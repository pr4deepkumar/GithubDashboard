locals {
  script_path = "${path.module}/scripts/fetch_github_dashboard.py"
}

data "external" "github_dashboard" {
  program = ["python3", local.script_path]

  query = {
    github_token          = var.github_token
    github_username       = var.github_username
    github_profile        = var.github_profile
    organizations_csv     = join(",", var.organizations)
    include_private       = tostring(var.include_private_repos)
    max_repositories      = tostring(var.max_repositories)
    max_items_per_section = tostring(var.max_items_per_section)
  }
}

locals {
  dashboard = jsondecode(data.external.github_dashboard.result.dashboard_json)
  rendered_dashboard = templatefile("${path.module}/templates/dashboard.html.tftpl", {
    generated_at   = data.external.github_dashboard.result.generated_at
    dashboard_json = jsonencode(local.dashboard)
  })
}

resource "local_file" "dashboard_html" {
  filename = var.output_file
  content  = local.rendered_dashboard
}
