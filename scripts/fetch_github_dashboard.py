#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def read_query():
  payload = sys.stdin.read().strip()
  if not payload:
    return {}
  return json.loads(payload)


def bool_from_string(value, default):
  if value is None:
    return default
  return str(value).strip().lower() in {"1", "true", "yes", "on"}


def int_from_string(value, default):
  try:
    return int(value)
  except (TypeError, ValueError):
    return default


def gh_get(url, token):
  headers = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "terraform-opentofu-github-dashboard",
  }
  if token:
    headers["Authorization"] = f"Bearer {token}"

  req = urllib.request.Request(
    url,
    headers=headers,
  )
  with urllib.request.urlopen(req, timeout=30) as resp:
    return json.loads(resp.read().decode("utf-8"))


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

  first_segment = path.split("/")[0]
  return first_segment.replace("@", "")


def collect_repositories(token, username, include_private, orgs, max_repositories):
  repos = []
  seen = set()

  if include_private:
    page = 1
    while len(repos) < max_repositories and page <= 5:
      url = (
        "https://api.github.com/user/repos"
        f"?sort=updated&per_page=100&page={page}"
      )
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
      url = (
        f"https://api.github.com/users/{urllib.parse.quote(username)}/repos"
        f"?sort=updated&per_page=100&page={page}"
      )
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
      url = (
        f"https://api.github.com/orgs/{urllib.parse.quote(org)}/repos"
        f"?sort=updated&per_page=100&page={page}"
      )
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
    output.append({
      "title": item.get("title", ""),
      "url": item.get("html_url", ""),
      "repo": (item.get("repository_url", "").split("/")[-2:] if item.get("repository_url") else ["", ""]),
      "updated_at": item.get("updated_at", ""),
    })
  for row in output:
    repo_parts = row["repo"]
    row["repo"] = "/".join(repo_parts) if isinstance(repo_parts, list) else str(repo_parts)
  return output[:limit]


def aggregate_languages(repos):
  lang_counts = {}
  for repo in repos:
    language = repo.get("language", "")
    if not language:
      continue
    lang_counts[language] = lang_counts.get(language, 0) + 1

  sorted_langs = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)
  return [{"name": name, "count": count} for name, count in sorted_langs[:6]]


def main():
  query = read_query()
  token = (query.get("github_token") or os.getenv("GITHUB_TOKEN") or "").strip()

  include_private = bool_from_string(query.get("include_private"), True)
  max_repositories = max(1, min(100, int_from_string(query.get("max_repositories"), 20)))
  max_items = max(1, min(100, int_from_string(query.get("max_items_per_section"), 20)))

  organizations_csv = query.get("organizations_csv", "")
  orgs = [x.strip() for x in organizations_csv.split(",") if x.strip()]

  username = resolve_username(query.get("github_profile", ""), query.get("github_username", ""))

  if not username and token:
    viewer = gh_get("https://api.github.com/user", token)
    username = viewer.get("login", "")
  if not username:
    raise ValueError("Could not resolve GitHub username. Set github_profile or github_username.")

  if not token:
    include_private = False

  profile = gh_get(f"https://api.github.com/users/{urllib.parse.quote(username)}", token)

  repos = collect_repositories(token, username, include_private, orgs, max_repositories)
  authored_prs = search_issues(token, f"is:pr is:open author:{username}", max_items)
  review_requested_prs = search_issues(token, f"is:pr is:open review-requested:{username}", max_items)
  assigned_issues = search_issues(token, f"is:issue is:open assignee:{username}", max_items)
  authored_issues = search_issues(token, f"is:issue is:open author:{username}", max_items)

  total_stars = sum(int(repo.get("stars", 0)) for repo in repos)
  languages = aggregate_languages(repos)

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

  result = {
    "dashboard_json": json.dumps(dashboard),
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
  }
  print(json.dumps(result))


if __name__ == "__main__":
  try:
    main()
  except urllib.error.HTTPError as err:
    message = err.read().decode("utf-8")
    print(json.dumps({"error": f"GitHub API error ({err.code}): {message}"}))
    sys.exit(1)
  except Exception as err:
    print(json.dumps({"error": str(err)}))
    sys.exit(1)
