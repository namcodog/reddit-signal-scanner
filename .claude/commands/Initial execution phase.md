First, initialize the project, follow the rules in our claude.md, use the workflow tool, and call the custom subagent to execute the task
Process of Task Execution，Architecture thinking first: The new pre-linus-check enables quick validation of directions before implementation, avoiding "writing complex code first and then refactoring".
60-second pre-review: Rapidly identify architectural pitfalls and detect issues in advance.
Collaborative optimization: Form a complete chain: task-analyzer → pre-linus-check → implementation → linus-architect.
Get it right the first time: Implement directly based on the pre-approved minimalist plan to avoid rework cycles.