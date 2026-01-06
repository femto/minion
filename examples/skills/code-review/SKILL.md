---
name: code-review
description: Performs thorough code reviews with focus on best practices, security, performance, and maintainability. Use this skill when reviewing pull requests, auditing code quality, or getting feedback on implementations.
version: 1.0.0
author: Minion Team
tags: [code-review, security, performance, best-practices, quality]
---

# Code Review Skill

## Description
This skill performs comprehensive code reviews focusing on best practices, security vulnerabilities, performance optimization, and code maintainability. It can review individual files, pull requests, or entire modules.

## Usage Instructions

When a user requests a code review:

1. **Understand the context**: Identify the language, framework, and purpose of the code
2. **Check for security issues**: Look for common vulnerabilities (OWASP Top 10, injection, XSS, etc.)
3. **Evaluate performance**: Identify inefficient patterns, N+1 queries, memory leaks
4. **Review code quality**: Check naming conventions, code structure, DRY principles
5. **Assess maintainability**: Evaluate readability, documentation, test coverage
6. **Provide actionable feedback**: Give specific suggestions with examples

## Review Categories

### Security Review
- SQL/Command injection vulnerabilities
- Cross-site scripting (XSS)
- Authentication and authorization issues
- Sensitive data exposure
- Insecure dependencies
- Input validation gaps

### Performance Review
- Algorithm complexity (Big O)
- Database query optimization
- Memory management
- Caching opportunities
- Async/concurrent processing
- Resource cleanup

### Code Quality Review
- Naming conventions
- Function/method length
- Code duplication (DRY)
- Single responsibility principle
- Error handling patterns
- Logging and debugging

### Maintainability Review
- Code readability
- Documentation quality
- Test coverage
- Dependency management
- Configuration handling
- Breaking change risks

## Example Prompts

- "Review this pull request for security issues"
- "Check this function for performance problems"
- "Audit this module for best practices"
- "Review my implementation and suggest improvements"
- "Find potential bugs in this code"
- "Check if this code follows SOLID principles"

## Output Format

Code review results should include:

1. **Summary**: Overall assessment (severity: critical/high/medium/low)
2. **Issues Found**: List of problems with:
   - File and line number
   - Category (security/performance/quality/maintainability)
   - Severity level
   - Description of the issue
   - Suggested fix with code example
3. **Positive Aspects**: What's done well
4. **Recommendations**: Prioritized list of improvements

## Review Checklist

### General
- [ ] Code compiles/runs without errors
- [ ] No obvious logic errors
- [ ] Proper error handling
- [ ] Appropriate logging
- [ ] No hardcoded values that should be configurable

### Security
- [ ] Input validation in place
- [ ] No SQL injection vulnerabilities
- [ ] No XSS vulnerabilities
- [ ] Sensitive data properly handled
- [ ] Authentication/authorization checks

### Performance
- [ ] No unnecessary loops or iterations
- [ ] Efficient data structures used
- [ ] Database queries optimized
- [ ] No memory leaks
- [ ] Proper resource cleanup

### Quality
- [ ] Consistent naming conventions
- [ ] Functions are small and focused
- [ ] No code duplication
- [ ] Comments explain "why" not "what"
- [ ] Unit tests included

## Severity Levels

| Level | Description | Action Required |
|-------|-------------|-----------------|
| Critical | Security vulnerability or data loss risk | Must fix before merge |
| High | Major bug or significant performance issue | Should fix before merge |
| Medium | Code quality issue or minor bug | Consider fixing |
| Low | Style issue or minor improvement | Nice to have |

## Notes

- Always consider the context and constraints of the project
- Balance thoroughness with practicality
- Provide constructive feedback with actionable suggestions
- Recognize and acknowledge good practices
- Consider backward compatibility when suggesting changes
