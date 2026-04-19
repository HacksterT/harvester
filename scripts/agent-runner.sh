#!/usr/bin/env bash
# ==============================================================================
# Harvester — Overnight Agent Runner
# ==============================================================================
# Drains the Harvester work queue by invoking Claude Code against each pending
# issue, producing a draft PR per issue. Invoked by launchd at 02:00 local time.
#
# Reads:
#   - data/queue/pending/*.json     (work items enqueued by webhook handler)
#   - harvester-config.yaml         (repo configurations, guarded paths)
#   - Each repo's CLAUDE.md         (agent system prompt for that repo)
#
# Writes:
#   - data/queue/completed/*.json   (successfully processed items)
#   - data/queue/failed/*.json      (items that errored)
#   - data/logs/run-YYYYMMDD-HHMMSS.log  (per-run log file)
#   - workspaces/<repo>-<num>/      (ephemeral per-issue workspace)
#   - GitHub branches and draft PRs on the target repos
#
# Authentication:
#   - Claude Code: subscription login on this Mac (not ANTHROPIC_API_KEY)
#   - GitHub: gh CLI authenticated separately (via `gh auth login`)
#
# Exit codes:
#   0  Success (may include per-item failures handled gracefully)
#   1  Preflight failed (claude unavailable, gh unauthenticated, etc.)
#   2  Config file missing or unparseable
#   3  Queue directory missing or inaccessible
# ==============================================================================

set -uo pipefail
# Note: deliberately NOT using `set -e`. We want the script to continue
# processing remaining queue items even if one item fails. Each item's
# failure is handled explicitly and logged; we do not want a single bad
# item to abort the entire overnight run.

# ------------------------------------------------------------------------------
# Configuration (paths resolved relative to Harvester repo root)
# ------------------------------------------------------------------------------

HARVESTER_ROOT="${HARVESTER_ROOT:-$HOME/Projects/harvester}"
QUEUE_DIR="$HARVESTER_ROOT/data/queue"
LOG_DIR="$HARVESTER_ROOT/data/logs"
WORKSPACES_DIR="${WORKSPACES_DIR:-$HOME/agent-workspaces}"
CONFIG_FILE="$HARVESTER_ROOT/harvester-config.yaml"

# Allow override via env; default to 30 minutes per item
DEFAULT_TIMEOUT_MINUTES="${HARVESTER_DEFAULT_TIMEOUT:-30}"
DEFAULT_MAX_TURNS="${HARVESTER_DEFAULT_MAX_TURNS:-50}"

# Telegram credentials (optional; from Ezra's env)
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_ALLOWED_CHAT_ID:-}"

# ------------------------------------------------------------------------------
# Logging setup — every run gets its own log file; also tee to stdout/stderr
# ------------------------------------------------------------------------------

mkdir -p "$LOG_DIR" "$WORKSPACES_DIR" \
    "$QUEUE_DIR/pending" "$QUEUE_DIR/completed" "$QUEUE_DIR/failed"

RUN_TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/run-$RUN_TIMESTAMP.log"

# Everything after this line gets tee'd to the log file as well as stdout.
# This is the one place we rely on bash's exec behavior for I/O redirection.
exec > >(tee -a "$LOG_FILE") 2>&1

# ------------------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------------------

log() {
    # Timestamped log line. All script output should go through this or echo.
    printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

log_section() {
    echo ""
    log "================================================================"
    log "$*"
    log "================================================================"
}

notify_telegram() {
    # Send a Telegram message. Silent if credentials aren't set.
    # Telegram is best-effort — never fail the run because notification failed.
    local message="$1"
    if [[ -z "$TELEGRAM_BOT_TOKEN" || -z "$TELEGRAM_CHAT_ID" ]]; then
        return 0
    fi
    curl -sS -X POST \
        "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$TELEGRAM_CHAT_ID" \
        -d "text=$message" \
        -d "parse_mode=Markdown" \
        > /dev/null 2>&1 || true
}

die() {
    # Fatal error — used only in preflight, not in the item loop.
    local exit_code="${2:-1}"
    log "FATAL: $1"
    notify_telegram "🔴 *Harvester preflight failed*
$1
Log: \`$LOG_FILE\`"
    exit "$exit_code"
}

# Safely read a field from a JSON file using jq. Returns empty string on missing.
json_field() {
    local file="$1"
    local path="$2"
    jq -r "$path // empty" "$file" 2>/dev/null || echo ""
}

# Read a repo-level config value from harvester-config.yaml using yq.
# Returns empty string on missing.
config_repo_field() {
    local repo_name="$1"
    local field="$2"
    yq -r ".repos[] | select(.name == \"$repo_name\") | $field // \"\"" \
        "$CONFIG_FILE" 2>/dev/null || echo ""
}

# Get the list of guarded-path globs for a repo.
config_repo_guarded_paths() {
    local repo_name="$1"
    yq -r ".repos[] | select(.name == \"$repo_name\") | .guarded_paths[]?" \
        "$CONFIG_FILE" 2>/dev/null
}

# Get the guarded-path policy for a repo.
# Returns: never_execute, warn, or empty (no policy).
config_repo_guarded_policy() {
    local repo_name="$1"
    yq -r ".repos[] | select(.name == \"$repo_name\") | .guarded_path_policy // \"\"" \
        "$CONFIG_FILE" 2>/dev/null
}

# Atomic move of a queue item from one folder to another.
# Uses `mv` which is atomic within the same filesystem.
move_queue_item() {
    local item_path="$1"
    local target_folder="$2"
    local target_name
    target_name="$(basename "$item_path")"
    local target_path="$QUEUE_DIR/$target_folder/$target_name"

    # If something already exists at the target, append run timestamp.
    if [[ -e "$target_path" ]]; then
        target_path="${target_path%.json}-$RUN_TIMESTAMP.json"
    fi

    mv "$item_path" "$target_path"
    log "Moved queue item to $target_folder/$(basename "$target_path")"
}

# Record a failure reason on the queue item before moving it.
annotate_failure() {
    local item_path="$1"
    local reason="$2"
    local detail="${3:-}"

    local tmp
    tmp="$(mktemp)"
    jq \
        --arg reason "$reason" \
        --arg detail "$detail" \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg log_file "$LOG_FILE" \
        '. + {failure: {reason: $reason, detail: $detail, timestamp: $timestamp, log_file: $log_file}}' \
        "$item_path" > "$tmp"
    mv "$tmp" "$item_path"
}

# ------------------------------------------------------------------------------
# Preflight — verify we can actually do anything before we try
# ------------------------------------------------------------------------------

preflight() {
    log_section "Preflight checks"

    # Required tools
    for tool in jq yq gh git claude curl; do
        if ! command -v "$tool" > /dev/null 2>&1; then
            die "Required tool '$tool' not found on PATH. PATH=$PATH"
        fi
        log "✓ $tool available at $(command -v "$tool")"
    done

    # Config file must exist and parse
    if [[ ! -f "$CONFIG_FILE" ]]; then
        die "Config file not found: $CONFIG_FILE" 2
    fi
    if ! yq '.' "$CONFIG_FILE" > /dev/null 2>&1; then
        die "Config file is not valid YAML: $CONFIG_FILE" 2
    fi
    log "✓ Config file parses: $CONFIG_FILE"

    # Queue directory structure
    if [[ ! -d "$QUEUE_DIR/pending" ]]; then
        die "Queue directory missing: $QUEUE_DIR/pending" 3
    fi
    log "✓ Queue directories exist under $QUEUE_DIR"

    # gh CLI authentication
    if ! gh auth status > /dev/null 2>&1; then
        die "gh CLI is not authenticated. Run: gh auth login"
    fi
    log "✓ gh CLI authenticated"

    # Claude Code subscription session
    # `claude --version` works offline; we need to verify auth actively.
    # The exit code of `claude` with no subcommand and a live session is 0.
    # With expired auth it returns non-zero or prints an auth prompt.
    if ! claude --version > /dev/null 2>&1; then
        die "claude CLI not functioning (check install)"
    fi
    log "✓ claude --version succeeds"

    # Deeper check: can we actually make a request? Cheapest way is to ask
    # Claude to echo a short string. Uses one subscription request but
    # catches stale auth before we start the expensive work.
    local auth_probe_output
    auth_probe_output="$(echo "Reply with just the word READY." \
        | claude --print --max-turns 1 2>&1)" || true

    if ! echo "$auth_probe_output" | grep -q "READY"; then
        die "Claude Code authentication appears stale.

Subscription session may have expired. To refresh:
  1. Run: claude
  2. Authenticate in the browser
  3. Exit the interactive session
  4. Re-invoke this script

Probe output was:
$auth_probe_output"
    fi
    log "✓ Claude Code subscription session is live"

    log_section "Preflight passed; proceeding to queue drain"
}

# ------------------------------------------------------------------------------
# Guarded path detection — compares the diff against repo's guarded paths
# ------------------------------------------------------------------------------

check_guarded_paths() {
    local repo_name="$1"
    local workspace="$2"

    local policy
    policy="$(config_repo_guarded_policy "$repo_name")"

    if [[ -z "$policy" ]]; then
        # No policy means no guarded paths; nothing to check.
        return 0
    fi

    # Get list of changed files vs. origin/main
    local changed_files
    changed_files="$(cd "$workspace" && git diff --name-only origin/main...HEAD)"

    if [[ -z "$changed_files" ]]; then
        log "No files changed in this run (empty diff)"
        return 0
    fi

    # Check each changed file against each guarded path glob
    local violations=()
    while IFS= read -r guarded_path; do
        [[ -z "$guarded_path" ]] && continue
        while IFS= read -r changed_file; do
            [[ -z "$changed_file" ]] && continue
            # Use bash extglob for glob matching
            # The ** pattern requires shopt -s globstar
            shopt -s globstar
            # shellcheck disable=SC2053
            if [[ "$changed_file" == $guarded_path ]]; then
                violations+=("$changed_file (matched by $guarded_path)")
            fi
        done <<< "$changed_files"
    done < <(config_repo_guarded_paths "$repo_name")

    if [[ ${#violations[@]} -eq 0 ]]; then
        log "✓ No guarded-path violations detected"
        return 0
    fi

    log "⚠ GUARDED-PATH VIOLATION DETECTED (${#violations[@]} file(s)):"
    for v in "${violations[@]}"; do
        log "    - $v"
    done

    if [[ "$policy" == "never_execute" ]]; then
        log "Policy is 'never_execute' — aborting this run"
        return 1
    elif [[ "$policy" == "warn" ]]; then
        log "Policy is 'warn' — proceeding but flagging heavily"
        return 0
    else
        log "Unknown policy '$policy' — treating as never_execute"
        return 1
    fi
}

# ------------------------------------------------------------------------------
# Process one queue item end-to-end
# ------------------------------------------------------------------------------

process_item() {
    local item_path="$1"
    local item_name
    item_name="$(basename "$item_path" .json)"

    log_section "Processing $item_name"

    # Parse the queue item
    local issue_num repo_github repo_name repo_local_path issue_title
    local max_turns branch_prefix claude_md_rel

    issue_num="$(json_field "$item_path" '.issue_number')"
    repo_github="$(json_field "$item_path" '.github_repo')"
    repo_name="$(json_field "$item_path" '.repo_name')"
    issue_title="$(json_field "$item_path" '.issue_title')"
    max_turns=""
    claude_md_rel=""

    # Defaults for any missing fields
    max_turns="${max_turns:-$DEFAULT_MAX_TURNS}"
    claude_md_rel="CLAUDE.md"
    branch_prefix="$(config_repo_field "$repo_name" '.branch_prefix')"
    branch_prefix="${branch_prefix:-improvement/}"

    log "issue_num      = $issue_num"
    log "repo_github    = $repo_github"
    log "repo_name      = $repo_name"
    log "branch_prefix  = $branch_prefix"
    log "max_turns      = $max_turns"
    log "claude_md      = $claude_md_rel"

    # Validate required fields
    if [[ -z "$issue_num" || -z "$repo_github" || -z "$repo_name" ]]; then
        log "ERROR: queue item missing required fields"
        annotate_failure "$item_path" "malformed_queue_item" \
            "Missing issue_number, repo, or repo_name"
        move_queue_item "$item_path" "failed"
        return 1
    fi

    # Workspace setup — fresh clone or hard reset
    local workspace="$WORKSPACES_DIR/$repo_name-$issue_num"

    if [[ -d "$workspace/.git" ]]; then
        log "Resetting existing workspace: $workspace"
        (
            cd "$workspace" || exit 1
            git fetch origin --quiet
            git checkout main --quiet 2>/dev/null || git checkout master --quiet
            git reset --hard origin/HEAD --quiet
            git clean -fd --quiet
        ) || {
            log "ERROR: workspace reset failed"
            annotate_failure "$item_path" "workspace_reset_failed"
            move_queue_item "$item_path" "failed"
            return 1
        }
    else
        log "Cloning fresh workspace: $workspace"
        rm -rf "$workspace"
        if ! gh repo clone "$repo_github" "$workspace" -- --quiet; then
            log "ERROR: clone failed"
            annotate_failure "$item_path" "clone_failed"
            gh issue comment "$issue_num" --repo "$repo_github" --body \
                "⚠️ Harvester agent run aborted: could not clone repo. See logs on Harvester host: \`$LOG_FILE\`" \
                || true
            move_queue_item "$item_path" "failed"
            return 1
        fi
    fi

    cd "$workspace" || {
        log "ERROR: cannot cd into workspace"
        annotate_failure "$item_path" "workspace_cd_failed"
        move_queue_item "$item_path" "failed"
        return 1
    }

    # Git identity for commits from this run
    git config user.name "harvester-agent"
    git config user.email "harvester-agent@users.noreply.github.com"

    # Create the working branch
    local branch_name="${branch_prefix}${issue_num}"
    log "Creating branch: $branch_name"

    # If a branch already exists from a prior failed run, delete it locally.
    git branch -D "$branch_name" > /dev/null 2>&1 || true

    if ! git checkout -b "$branch_name" --quiet; then
        log "ERROR: branch creation failed"
        annotate_failure "$item_path" "branch_creation_failed"
        move_queue_item "$item_path" "failed"
        return 1
    fi

    # Fetch the full issue body from GitHub
    local issue_body_file="/tmp/harvester-issue-$issue_num.md"
    log "Fetching issue body from GitHub"
    if ! gh issue view "$issue_num" --repo "$repo_github" \
            --json body -q .body > "$issue_body_file"; then
        log "ERROR: could not fetch issue body"
        annotate_failure "$item_path" "issue_fetch_failed"
        move_queue_item "$item_path" "failed"
        return 1
    fi

    # Build the task spec for Claude Code
    local task_file="/tmp/harvester-task-$issue_num.md"
    local claude_md_path="$workspace/$claude_md_rel"

    cat > "$task_file" <<EOF
# Harvester Agent Task

You are working on GitHub issue #$issue_num in the repository $repo_github.

## Issue Title
$issue_title

## Issue Body
$(cat "$issue_body_file")

## Your Instructions

1. **Read $claude_md_rel first.** It contains repository-specific conventions
   you must follow.

2. **Stay within scope.** Address the Acceptance Criteria stated in the issue.
   Do not expand scope. If you identify adjacent work, note it in your commit
   message as a follow-up.

3. **Test before you commit.** Run the project's test suite. If tests fail,
   either fix your implementation or explain clearly why the task cannot be
   completed as specified.

4. **Commit your work, but do not push.** This script will handle the push
   and PR creation after you exit cleanly.

5. **If you cannot complete the task**, commit whatever partial progress you
   have with a commit message that explains clearly what is incomplete and
   why. Exit with a partial result rather than forcing a broken solution.

6. **You may NOT modify files in guarded paths.** This repository has
   guarded-path protection. Any changes to files under protected paths will
   cause this run to be aborted automatically.

When you are finished (successful or not), exit.
EOF

    # Invoke Claude Code
    log "Invoking Claude Code (max_turns=$max_turns, timeout=${DEFAULT_TIMEOUT_MINUTES}m)"
    local claude_start
    claude_start="$(date +%s)"

    # The `timeout` command here is a hard ceiling. Claude Code's own
    # max_turns provides a softer ceiling. In practice max_turns will hit
    # first; timeout is the failsafe.
    local claude_exit_code=0
    timeout "${DEFAULT_TIMEOUT_MINUTES}m" \
        claude -p --max-turns "$max_turns" < "$task_file" \
        || claude_exit_code=$?

    local claude_end
    claude_end="$(date +%s)"
    local claude_duration=$((claude_end - claude_start))

    log "Claude Code exited with code $claude_exit_code after ${claude_duration}s"

    # Special exit codes:
    #   0   — normal exit
    #   124 — timeout fired
    #   others — Claude Code error
    if [[ $claude_exit_code -eq 124 ]]; then
        log "ERROR: Claude Code hit the ${DEFAULT_TIMEOUT_MINUTES}-minute timeout"
        annotate_failure "$item_path" "claude_timeout" \
            "Exceeded ${DEFAULT_TIMEOUT_MINUTES}-minute timeout"
        gh issue comment "$issue_num" --repo "$repo_github" --body \
            "⚠️ Harvester agent run timed out after ${DEFAULT_TIMEOUT_MINUTES} minutes. The task may be too large for a single run, or the agent got stuck. See logs: \`$LOG_FILE\`" \
            || true
        move_queue_item "$item_path" "failed"
        return 1
    elif [[ $claude_exit_code -ne 0 ]]; then
        log "ERROR: Claude Code exited with non-zero status"
        annotate_failure "$item_path" "claude_error" \
            "Exit code: $claude_exit_code"
        gh issue comment "$issue_num" --repo "$repo_github" --body \
            "⚠️ Harvester agent run failed during Claude Code execution (exit $claude_exit_code). See logs: \`$LOG_FILE\`" \
            || true
        move_queue_item "$item_path" "failed"
        return 1
    fi

    # Verify Claude actually made commits
    local commit_count
    commit_count="$(git rev-list --count origin/main..HEAD 2>/dev/null || \
                    git rev-list --count origin/master..HEAD 2>/dev/null || \
                    echo 0)"
    if [[ "$commit_count" -eq 0 ]]; then
        log "ERROR: Claude Code produced no commits"
        annotate_failure "$item_path" "no_commits" \
            "Agent exited cleanly but made no commits"
        gh issue comment "$issue_num" --repo "$repo_github" --body \
            "⚠️ Harvester agent ran to completion but produced no commits. The task may have been ambiguous or unimplementable. See logs: \`$LOG_FILE\`" \
            || true
        move_queue_item "$item_path" "failed"
        return 1
    fi
    log "✓ Claude Code produced $commit_count commit(s)"

    # Guarded-path enforcement — CRITICAL for Selah
    log "Checking diff against guarded paths"
    if ! check_guarded_paths "$repo_name" "$workspace"; then
        log "ERROR: guarded-path violation; aborting without pushing"
        annotate_failure "$item_path" "guarded_path_violation" \
            "Agent changed files in guarded paths; run refused"

        # Loud notification — this should never happen; if it does it's notable
        notify_telegram "🚨 *GUARDED PATH VIOLATION*
Issue #$issue_num in $repo_name
Agent attempted to change protected files. Run aborted before push.
Log: \`$LOG_FILE\`

This is noteworthy. Investigate the scanner and enqueue logic."

        gh issue comment "$issue_num" --repo "$repo_github" --body \
            "🚨 Harvester agent run aborted: proposed changes touched guarded paths. This change requires manual review and implementation by the repository owner. See logs: \`$LOG_FILE\`" \
            || true

        # Clean up the branch locally; never push it
        git checkout main --quiet 2>/dev/null || git checkout master --quiet
        git branch -D "$branch_name" --quiet

        move_queue_item "$item_path" "failed"
        return 1
    fi

    # Push the branch
    log "Pushing branch to origin"
    if ! git push -u origin "$branch_name" --quiet; then
        log "ERROR: push failed"
        annotate_failure "$item_path" "push_failed"
        gh issue comment "$issue_num" --repo "$repo_github" --body \
            "⚠️ Harvester agent completed but could not push the branch. See logs: \`$LOG_FILE\`" \
            || true
        move_queue_item "$item_path" "failed"
        return 1
    fi

    # Open the draft PR
    log "Opening draft PR"
    local pr_body_file="/tmp/harvester-pr-body-$issue_num.md"
    local last_commit_msg
    last_commit_msg="$(git log -1 --format=%B)"

    cat > "$pr_body_file" <<EOF
## Automated implementation of #$issue_num

This PR was produced by the Harvester overnight agent runner. See the original
issue for context and acceptance criteria.

### What Claude Code did

$last_commit_msg

### Review checklist

- [ ] Diff matches the issue's acceptance criteria
- [ ] Tests pass locally
- [ ] Code follows conventions in \`$claude_md_rel\`
- [ ] No unintended scope expansion
- [ ] Commit messages are clear

### Run details

- Run timestamp: $RUN_TIMESTAMP
- Claude Code duration: ${claude_duration}s
- Commits in branch: $commit_count
- Workspace: \`$workspace\`
- Log file: \`$LOG_FILE\`

Closes #$issue_num
EOF

    local pr_url
    pr_url="$(gh pr create \
        --repo "$repo_github" \
        --draft \
        --title "Closes #$issue_num: $issue_title" \
        --body-file "$pr_body_file" \
        2>&1)" || {
        log "ERROR: PR creation failed"
        log "$pr_url"
        annotate_failure "$item_path" "pr_creation_failed" "$pr_url"
        gh issue comment "$issue_num" --repo "$repo_github" --body \
            "⚠️ Harvester agent pushed the branch but could not create the PR. See logs: \`$LOG_FILE\`" \
            || true
        move_queue_item "$item_path" "failed"
        return 1
    }

    log "✓ Draft PR created: $pr_url"

    # Success — move to completed and record the PR URL
    local tmp
    tmp="$(mktemp)"
    jq \
        --arg pr_url "$pr_url" \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg log_file "$LOG_FILE" \
        --arg duration "$claude_duration" \
        --arg commits "$commit_count" \
        '. + {completion: {pr_url: $pr_url, completed_at: $timestamp, log_file: $log_file, claude_duration_sec: ($duration | tonumber), commit_count: ($commits | tonumber)}}' \
        "$item_path" > "$tmp"
    mv "$tmp" "$item_path"

    move_queue_item "$item_path" "completed"

    # Per-item Telegram notification (light touch)
    notify_telegram "✓ Harvester: PR opened for #$issue_num ($repo_name)
$pr_url"

    return 0
}

# ------------------------------------------------------------------------------
# Main drain loop
# ------------------------------------------------------------------------------

main() {
    log_section "Harvester agent runner starting at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    log "Run timestamp: $RUN_TIMESTAMP"
    log "Log file: $LOG_FILE"

    preflight

    # Snapshot the pending queue at start.
    # Using find (not glob) avoids issues with empty directories.
    local pending_items=()
    while IFS= read -r -d '' item; do
        pending_items+=("$item")
    done < <(find "$QUEUE_DIR/pending" -maxdepth 1 -name '*.json' -print0 \
             | sort -z)

    local total_count=${#pending_items[@]}
    log "Pending queue depth: $total_count"

    if [[ $total_count -eq 0 ]]; then
        log "Queue is empty. Nothing to do."
        log_section "Harvester agent runner finished at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        notify_telegram "Harvester: overnight run complete — queue was empty"
        exit 0
    fi

    local success_count=0
    local failure_count=0

    for item in "${pending_items[@]}"; do
        if [[ ! -f "$item" ]]; then
            # Item may have been moved already (unlikely in practice)
            log "Skipping $item (no longer present)"
            continue
        fi

        if process_item "$item"; then
            success_count=$((success_count + 1))
        else
            failure_count=$((failure_count + 1))
        fi

        # Return to Harvester root between items so relative paths stay sane
        cd "$HARVESTER_ROOT" || die "Cannot return to Harvester root"
    done

    log_section "Run summary"
    log "Total items processed: $total_count"
    log "Succeeded:             $success_count"
    log "Failed:                $failure_count"
    log "Log file:              $LOG_FILE"

    local summary
    summary="*Harvester overnight run complete*
Processed: $total_count
Succeeded: $success_count
Failed: $failure_count"

    if [[ $failure_count -gt 0 ]]; then
        summary="$summary

Check \`$QUEUE_DIR/failed/\` for details."
    fi

    notify_telegram "$summary"

    log_section "Harvester agent runner finished at $(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # Exit 0 even if some items failed — the script completed its job
    # (drain the queue). Per-item failures are tracked in failed/ folder.
    exit 0
}

main "$@"
