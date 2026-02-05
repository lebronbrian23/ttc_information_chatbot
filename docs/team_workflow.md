═══════════════════════════════════════════════

      TTC CHATBOT - WORKFLOW CHEAT SHEET

═══════════════════════════════════════════════

WEEKLY:
Post online check-in/sync by Thursday 6pm via (LinkedIn/Slack)
 - What I did this week 
 - What I'm doing next week
 - Any blockers

STARTING NEW WORK:
1. git checkout develop
2. git pull origin develop
3. git checkout -b feature/my-feature
4. Work on your feature
5. git add . && git commit -m "feat: description"
6. git push origin feature/my-feature
7. Create PR on GitHub
8. Assign reviewer(s)

REVIEWING A PR:
1. Read the description
2. Pull the branch locally: git checkout feature/their-feature
3. Test it
4. Leave comments on GitHub (be nice!)
5. Approve or request changes

WHEN YOUR PR IS APPROVED:
1. Merge to develop
2. Delete your feature branch
3. Pull latest develop: git pull origin develop
4. Start next feature

Bi-WEEKLY MEETINGS:
- Sprint Planning (every 2 weeks): Plan what to build
- Sprint Review (every 2 weeks): Demo what you built
- Weekly Sync (online): Discuss blockers, alignment

COMMUNICATION:
- Quick questions → Slack/LinkedIn DM or #tech-discussion
- PR feedback → GitHub comments
- Blockers → Tag person in #standup
- Decisions → #tech-discussion + document

═══════════════════════════════════════════════



**By following this workflow, we'll practice:**

1. ✅ **Git branching strategies** (used by 95% of companies)
2. ✅ **Pull request/code review process** (how all teams work remotely)
3. ✅ **Agile/Scrum basics** (2-week sprints, standups, retrospectives)
4. ✅ **CI/CD concepts** (automated testing and deployment)
5. ✅ **Collaborative coding** (working in parallel without conflicts)
6. ✅ **Documentation practices** (writing code others can understand)
7. ✅ **Communication skills** (async standup, PR comments, technical discussion)

**Possible Resume bullet points:**
- Worked in Agile team using Git branching, PR reviews, and CI/CD
- Participated in sprint planning, daily standups, and retrospectives
- Reviewed code and provided constructive feedback in collaborative environment


**Key Practices We'll Implement:**

1. ✅ **Feature branches** - Work in isolation, merge when ready
2. ✅ **Pull Requests (PRs)** - Code review before merging
3. ✅ **Sprint planning** - 2-week cycles with clear goals
4. ✅ **Daily standups** - Quick async check-ins (not meetings)
5. ✅ **Code reviews** - Learn from each other, catch bugs
6. ✅ **CI/CD** - Automated testing and deployment
7. ✅ **Documentation** - Write as you build


**Sprint Schedule:**

| Sprint | Weeks | Goal |
|--------|-------|------|
| **Sprint 1** | Weeks 2-3 | Initial setup: Data pipeline, DB schema, basic backend |
| **Sprint 2** | Weeks 4-5 | Integration: Connect data → backend → frontend, simple model |
| **Sprint 3** | Weeks 6-7 | Phase 1 complete: Working chatbot with predictions |
| **Sprint 4** | Weeks 8-9 | Phase 2 start: Advanced models, RAG, visualizations |
| **Sprint 5** | Weeks 10-11 | Phase 2 polish: Testing, optimization, monitoring |
| **Sprint 6** | Weeks 12-13 | Final: Documentation, demo prep, bug fixes |
