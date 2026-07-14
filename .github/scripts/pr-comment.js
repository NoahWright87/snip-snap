// Shared helper for posting/updating a single PR comment across workflow
// runs, keyed by a hidden marker in the comment body (find-or-create,
// Netlify-deploy-comment style) instead of spamming a new comment per push.

const MARKER = "<!-- snip-snap-preview-build -->";

async function upsertComment({ github, context, body }) {
  const issue_number = context.issue.number;
  const { owner, repo } = context.repo;
  const fullBody = `${body}\n\n${MARKER}`;

  const comments = await github.rest.issues.listComments({ owner, repo, issue_number });
  const existing = comments.data.find((c) => c.body && c.body.includes(MARKER));

  if (existing) {
    await github.rest.issues.updateComment({ owner, repo, comment_id: existing.id, body: fullBody });
  } else {
    await github.rest.issues.createComment({ owner, repo, issue_number, body: fullBody });
  }
}

module.exports = { upsertComment };
