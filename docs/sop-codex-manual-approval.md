# Standard Operating Procedure: Handling Codex Manual Approval Tasks

## Purpose
This document defines the standard operating procedure for handling Codex tasks that require manual approval and block the automation pipeline.

## Background
When Codex is used to automate tasks (such as resolving merge conflicts or updating sync helpers), it may generate a task that requires manual approval before execution. Currently, there is no mechanism to approve these tasks via automated triggers or reactions to bot comments. This creates a blocker in the CI/CD pipeline, preventing subsequent automation from proceeding without human intervention.

## Scope
This SOP applies to all PR-CYBR team members working with the PR-CYBR-DATA-INTEGRATION-AGENT and other repositories where Codex automation is employed.

## Procedure

### When a Codex Task Requires Manual Approval

1. **Identify the Blocked Task**
   - Monitor pull requests for Codex bot comments indicating a task has been created
   - Look for pending tasks that are awaiting approval in the Codex interface
   - Note the PR number and task description

2. **Create a GitHub Issue to Track the Blocker**
   
   When a Codex task blocks the automation pipeline, immediately create a GitHub issue with the following information:
   
   **Issue Title Format:**
   ```
   [CODEX-APPROVAL-REQUIRED] Task blocked for PR #{PR_NUMBER}: {Brief Description}
   ```
   
   **Issue Body Template:**
   ```markdown
   ## Summary
   A Codex task requires manual approval and is blocking the automation pipeline.
   
   ## Details
   - **Pull Request:** #{PR_NUMBER}
   - **Task Description:** {Description of what the Codex task is attempting to do}
   - **Codex Bot Comment Link:** {URL to the bot comment}
   - **Date/Time Detected:** {Timestamp}
   
   ## Required Action
   - [ ] Review the Codex task in the Codex interface
   - [ ] Approve or reject the task
   - [ ] Monitor for task completion
   - [ ] Close this issue once the task is resolved
   
   ## Context
   This task is part of the automation chain and subsequent workflows cannot proceed until this is resolved.
   ```
   
   **Issue Labels:**
   - `codex-approval`
   - `automation-blocked`
   - `high-priority`

3. **Notify Relevant Team Members**
   - Assign the issue to the appropriate team member(s)
   - Mention team members in the issue if immediate attention is required
   - Post in relevant communication channels (Slack, Teams, etc.) if the blocker is time-sensitive

4. **Manually Approve the Task**
   - Navigate to the Codex interface
   - Review the proposed changes or actions
   - Approve the task if the changes are acceptable
   - Reject and provide feedback if changes are needed

5. **Monitor Task Completion**
   - Watch for the Codex task to complete after approval
   - Verify that the automation pipeline resumes
   - Check that subsequent CI/CD workflows execute successfully

6. **Close the Tracking Issue**
   - Once the task completes and the pipeline resumes, close the GitHub issue
   - Document any lessons learned or issues encountered in a comment before closing

## Best Practices

### Preventive Measures
- **Review Automation Scope:** Before delegating tasks to Codex, consider whether the task requires manual review or can be fully automated
- **Task Complexity:** Simple, well-defined tasks (like formatting, linting fixes) are better candidates for full automation than complex logic changes
- **Regular Monitoring:** Set up notifications for Codex bot comments to catch blocked tasks early

### Issue Management
- **Keep Issues Updated:** Add comments to tracking issues as status changes
- **Tag Related PRs:** Link the tracking issue to the related pull request
- **Review Patterns:** Periodically review closed tracking issues to identify patterns in what tasks commonly require approval

## Future Enhancements

The following enhancements could reduce or eliminate the need for this manual process:

1. **Automated Approval Mechanism**
   - Implement automatic approval after a time delay for low-risk tasks
   - Support approval via GitHub reactions or comments
   - Allow configuration of auto-approval rules based on task type

2. **Workflow Integration**
   - Create a GitHub Action workflow that automatically creates tracking issues when Codex tasks are pending
   - Implement webhooks or polling to detect pending Codex tasks
   - Send notifications through existing communication channels

3. **Task Classification**
   - Categorize Codex tasks by risk level
   - Auto-approve low-risk tasks (e.g., documentation updates, formatting)
   - Require manual review only for high-risk changes (e.g., logic modifications, security-sensitive code)

## Related Documentation
- [GitHub Actions Overview](agent-actions.md)
- [Notion Sync Integration](integrations/notion-sync.md)
- [PR-CYBR Data Integration Agent Documentation](PR-CYBR-DATA-INTEGRATION-AGENT.md)

## Revision History
| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-25 | 1.0 | Initial SOP creation | PR-CYBR Team |
