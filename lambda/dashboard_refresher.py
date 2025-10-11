#!/usr/bin/env python3
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime

import boto3


def bool_from_string(value, default):
  if value is None:
    return default
  return str(value).strip().lower() in {"1", "true", "yes", "on"}


def int_from_string(value, default):
  try:
    return int(value)
  except (TypeError, ValueError):
    return default


def resolve_username(profile_or_username, fallback_username):
  candidate = (profile_or_username or fallback_username or "").strip()
  if not candidate:
    return ""

  if "github.com/" not in candidate:
    return candidate.replace("@", "").strip("/")

  parsed = urllib.parse.urlparse(candidate)
  path = parsed.path.strip("/")
  if not path:
    return ""

  return path.split("/")[0].replace("@", "")


def gh_get(url, token):
  headers = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "github-dashboard-lambda-refresh",
  }
  if token:
    headers["Authorization"] = f"Bearer {token}"

  req = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(req, timeout=30) as resp:
    return json.loads(resp.read().decode("utf-8"))


def collect_repositories(token, username, include_private, orgs, max_repositories):
  repos = []
  seen = set()

  if include_private:
    page = 1
    while len(repos) < max_repositories and page <= 5:
      url = f"https://api.github.com/user/repos?sort=updated&per_page=100&page={page}"
      chunk = gh_get(url, token)
      if not chunk:
        break
      for repo in chunk:
        full_name = repo.get("full_name", "")
        if full_name in seen:
          continue
        seen.add(full_name)
        repos.append({
          "name": full_name,
          "url": repo.get("html_url", ""),
          "updated_at": repo.get("updated_at", ""),
          "stars": repo.get("stargazers_count", 0),
          "open_issues": repo.get("open_issues_count", 0),
          "language": repo.get("language", ""),
          "visibility": "private" if repo.get("private") else "public",
        })
        if len(repos) >= max_repositories:
          break
      page += 1
  else:
    page = 1
    while len(repos) < max_repositories and page <= 5:
      url = f"https://api.github.com/users/{urllib.parse.quote(username)}/repos?sort=updated&per_page=100&page={page}"
      chunk = gh_get(url, token)
      if not chunk:
        break
      for repo in chunk:
        full_name = repo.get("full_name", "")
        if full_name in seen:
          continue
        seen.add(full_name)
        repos.append({
          "name": full_name,
          "url": repo.get("html_url", ""),
          "updated_at": repo.get("updated_at", ""),
          "stars": repo.get("stargazers_count", 0),
          "open_issues": repo.get("open_issues_count", 0),
          "language": repo.get("language", ""),
          "visibility": "private" if repo.get("private") else "public",
        })
        if len(repos) >= max_repositories:
          break
      page += 1

  for org in orgs:
    if len(repos) >= max_repositories:
      break
    page = 1
    while len(repos) < max_repositories and page <= 3:
      url = f"https://api.github.com/orgs/{urllib.parse.quote(org)}/repos?sort=updated&per_page=100&page={page}"
      chunk = gh_get(url, token)
      if not chunk:
        break
      for repo in chunk:
        full_name = repo.get("full_name", "")
        if full_name in seen:
          continue
        seen.add(full_name)
        repos.append({
          "name": full_name,
          "url": repo.get("html_url", ""),
          "updated_at": repo.get("updated_at", ""),
          "stars": repo.get("stargazers_count", 0),
          "open_issues": repo.get("open_issues_count", 0),
          "language": repo.get("language", ""),
          "visibility": "private" if repo.get("private") else "public",
        })
        if len(repos) >= max_repositories:
          break
      page += 1

  repos.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
  return repos[:max_repositories]


def search_issues(token, query, limit):
  q = urllib.parse.quote(query)
  url = f"https://api.github.com/search/issues?q={q}&sort=updated&order=desc&per_page={limit}"
  data = gh_get(url, token)
  items = data.get("items", [])
  output = []
  for item in items:
    repo = item.get("repository_url", "").split("/")[-2:]
    output.append({
      "title": item.get("title", ""),
      "url": item.get("html_url", ""),
      "repo": "/".join(repo),
      "updated_at": item.get("updated_at", ""),
    })
  return output[:limit]


def aggregate_languages(repos):
  counts = {}
  for repo in repos:
    language = repo.get("language", "")
    if language:
      counts[language] = counts.get(language, 0) + 1
  return [{"name": name, "count": count} for name, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:6]]


def render_html(generated_at, dashboard):
  dashboard_json = json.dumps(dashboard)
  return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GitHub Dashboard</title>
  <style>
    :root {{ --bg:#0c1018; --card:#141b28; --line:#23314c; --text:#e6ecf7; --muted:#9fb0cc; --accent:#3dd4a7; --link:#8ab7ff; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--text); background:radial-gradient(1200px 500px at 20% -10%, #22345d 0%, var(--bg) 55%); }}
    .wrap {{ width:min(1150px,92vw); margin:24px auto 48px; }}
    .top {{ display:flex; justify-content:space-between; align-items:end; gap:12px; margin-bottom:20px; }}
    .summary {{ display:grid; grid-template-columns:repeat(6,minmax(120px,1fr)); gap:10px; margin-bottom:16px; }}
    .profile-card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px; margin-bottom:14px; display:flex; align-items:center; gap:12px; }}
    .avatar {{ width:56px; height:56px; border-radius:50%; border:1px solid var(--line); object-fit:cover; background:#0f1522; }}
    .profile-title {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
    .metric {{ background:linear-gradient(180deg,rgba(255,255,255,0.02),transparent),var(--card); border:1px solid var(--line); border-radius:12px; padding:12px; }}
    .metric .label {{ color:var(--muted); font-size:.78rem; }}
    .metric .value {{ margin-top:6px; color:var(--accent); font-weight:700; font-size:1.35rem; }}
    .grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
    .panel {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px; min-height:220px; }}
    ul {{ margin:0; padding:0; list-style:none; display:flex; flex-direction:column; gap:8px; }}
    li {{ border:1px solid var(--line); border-radius:10px; padding:10px; background:rgba(255,255,255,.01); }}
    a {{ color:var(--link); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
    .subtle,.meta,.empty {{ color:var(--muted); }} .meta {{ margin-top:6px; display:flex; flex-wrap:wrap; gap:10px; font-size:.82rem; }}
    .empty {{ font-style:italic; margin-top:14px; }}
    @media (max-width:920px) {{ .summary {{ grid-template-columns:repeat(2,minmax(120px,1fr)); }} .grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="top">
      <div>
        <h1 id="title">GitHub Dashboard</h1>
        <p class="subtle">Generated at {generated_at}</p>
      </div>
    </section>
    <section id="profile" class="profile-card"></section>
    <section id="summary" class="summary"></section>
    <section id="panels" class="grid"></section>
  </main>
  <script>
    const dashboard = {dashboard_json};
    const summaryFields = [
      ["Repos Listed", dashboard.summary.repositories],
      ["Public Repos", dashboard.profile.public_repos],
      ["Followers", dashboard.profile.followers],
      ["Open PRs Authored", dashboard.summary.authored_prs],
      ["Open Issues Authored", dashboard.summary.authored_issues],
      ["Stars (Listed Repos)", dashboard.summary.repo_stars]
    ];
    const topLanguages = (dashboard.languages || []).map((x) => `${{x.name}} (${{x.count}})`).join(", ");
    const panels = [
      {{ title:"Recently Updated Repositories", empty:"No repositories found.", items:dashboard.recent_repositories, renderItem:(item)=>`<a href="${{item.url}}" target="_blank" rel="noreferrer">${{item.name}}</a><div class="meta"><span>Updated: ${{item.updated_at}}</span><span>Stars: ${{item.stars}}</span><span>Open issues: ${{item.open_issues}}</span><span>Language: ${{item.language || "n/a"}}</span><span>${{item.visibility}}</span></div>` }},
      {{ title:"Open PRs Authored", empty:"No open authored pull requests.", items:dashboard.authored_prs, renderItem:(item)=>`<a href="${{item.url}}" target="_blank" rel="noreferrer">${{item.title}}</a><div class="meta"><span>${{item.repo}}</span><span>Updated: ${{item.updated_at}}</span></div>` }},
      {{ title:"PRs Requesting Review", empty:"No review requests right now.", items:dashboard.review_requested_prs, renderItem:(item)=>`<a href="${{item.url}}" target="_blank" rel="noreferrer">${{item.title}}</a><div class="meta"><span>${{item.repo}}</span><span>Updated: ${{item.updated_at}}</span></div>` }},
      {{ title:"Top Languages (Listed Repositories)", empty:"No languages found.", items:dashboard.languages, renderItem:(item)=>`<strong>${{item.name}}</strong><div class="meta"><span>Repositories: ${{item.count}}</span></div>` }},
      {{ title:"Assigned Open Issues", empty:"No assigned issues.", items:dashboard.assigned_issues, renderItem:(item)=>`<a href="${{item.url}}" target="_blank" rel="noreferrer">${{item.title}}</a><div class="meta"><span>${{item.repo}}</span><span>Updated: ${{item.updated_at}}</span></div>` }},
      {{ title:"Authored Open Issues", empty:"No authored open issues.", items:dashboard.authored_issues, renderItem:(item)=>`<a href="${{item.url}}" target="_blank" rel="noreferrer">${{item.title}}</a><div class="meta"><span>${{item.repo}}</span><span>Updated: ${{item.updated_at}}</span></div>` }}
    ];
    document.getElementById("title").textContent = `GitHub Dashboard for ${{dashboard.username}}`;
    document.getElementById("profile").innerHTML = `
      <img class="avatar" src="${{dashboard.profile.avatar_url}}" alt="${{dashboard.username}} avatar" />
      <div>
        <div class="profile-title">
          <a href="${{dashboard.profile.html_url}}" target="_blank" rel="noreferrer">${{dashboard.profile.name}}</a>
          <span class="subtle">@${{dashboard.username}}</span>
        </div>
        <div class="meta">
          ${{dashboard.profile.company ? `<span>Company: ${{dashboard.profile.company}}</span>` : ""}}
          ${{dashboard.profile.location ? `<span>Location: ${{dashboard.profile.location}}</span>` : ""}}
          <span>Following: ${{dashboard.profile.following}}</span>
          ${{topLanguages ? `<span>Top langs: ${{topLanguages}}</span>` : ""}}
        </div>
        ${{dashboard.profile.bio ? `<p class="subtle">${{dashboard.profile.bio}}</p>` : ""}}
      </div>
    `;
    const summaryNode = document.getElementById("summary");
    summaryFields.forEach(([label, value]) => {{
      const metric = document.createElement("div");
      metric.className = "metric";
      metric.innerHTML = `<div class="label">${{label}}</div><div class="value">${{value}}</div>`;
      summaryNode.appendChild(metric);
    }});
    const panelsNode = document.getElementById("panels");
    panels.forEach((panel) => {{
      const article = document.createElement("article");
      article.className = "panel";
      const title = document.createElement("h2");
      title.textContent = panel.title;
      article.appendChild(title);
      if (!panel.items || panel.items.length === 0) {{
        const empty = document.createElement("p");
        empty.className = "empty";
        empty.textContent = panel.empty;
        article.appendChild(empty);
      }} else {{
        const list = document.createElement("ul");
        panel.items.forEach((item) => {{
          const row = document.createElement("li");
          row.innerHTML = panel.renderItem(item);
          list.appendChild(row);
        }});
        article.appendChild(list);
      }}
      panelsNode.appendChild(article);
    }});
  </script>
</body>
</html>"""


def handler(event, context):
  token = (os.getenv("GITHUB_TOKEN") or "").strip()
  include_private = bool_from_string(os.getenv("INCLUDE_PRIVATE"), True)
  max_repositories = max(1, min(100, int_from_string(os.getenv("MAX_REPOSITORIES"), 20)))
  max_items = max(1, min(100, int_from_string(os.getenv("MAX_ITEMS_PER_SECTION"), 20)))
  organizations_csv = os.getenv("ORGANIZATIONS_CSV", "")
  orgs = [x.strip() for x in organizations_csv.split(",") if x.strip()]

  username = resolve_username(os.getenv("TARGET_GITHUB_PROFILE", ""), os.getenv("TARGET_GITHUB_USERNAME", ""))
  if not username and token:
    viewer = gh_get("https://api.github.com/user", token)
    username = viewer.get("login", "")
  if not username:
    raise ValueError("Could not resolve GitHub username. Configure TARGET_GITHUB_PROFILE or TARGET_GITHUB_USERNAME.")

  if not token:
    include_private = False

  profile = gh_get(f"https://api.github.com/users/{urllib.parse.quote(username)}", token)
  repos = collect_repositories(token, username, include_private, orgs, max_repositories)
  authored_prs = search_issues(token, f"is:pr is:open author:{username}", max_items)
  review_requested_prs = search_issues(token, f"is:pr is:open review-requested:{username}", max_items)
  assigned_issues = search_issues(token, f"is:issue is:open assignee:{username}", max_items)
  authored_issues = search_issues(token, f"is:issue is:open author:{username}", max_items)
  languages = aggregate_languages(repos)
  total_stars = sum(int(repo.get("stars", 0)) for repo in repos)

  dashboard = {
    "username": username,
    "profile": {
      "name": profile.get("name", "") or username,
      "bio": profile.get("bio", ""),
      "avatar_url": profile.get("avatar_url", ""),
      "html_url": profile.get("html_url", f"https://github.com/{username}"),
      "followers": profile.get("followers", 0),
      "following": profile.get("following", 0),
      "public_repos": profile.get("public_repos", 0),
      "company": profile.get("company", ""),
      "location": profile.get("location", ""),
    },
    "summary": {
      "repositories": len(repos),
      "authored_prs": len(authored_prs),
      "review_requested_prs": len(review_requested_prs),
      "assigned_issues": len(assigned_issues),
      "authored_issues": len(authored_issues),
      "repo_stars": total_stars,
    },
    "languages": languages,
    "recent_repositories": repos,
    "authored_prs": authored_prs,
    "review_requested_prs": review_requested_prs,
    "assigned_issues": assigned_issues,
    "authored_issues": authored_issues,
  }

  generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
  html = render_html(generated_at, dashboard)

  bucket = os.getenv("OUTPUT_BUCKET", "").strip()
  key = os.getenv("OUTPUT_KEY", "index.html").strip()
  if not bucket:
    raise ValueError("OUTPUT_BUCKET is required.")

  s3 = boto3.client("s3")
  s3.put_object(
    Bucket=bucket,
    Key=key,
    Body=html.encode("utf-8"),
    ContentType="text/html; charset=utf-8",
  )

  return {
    "statusCode": 200,
    "body": json.dumps({
      "message": "Dashboard refreshed",
      "bucket": bucket,
      "key": key,
      "username": username,
    }),
  }
