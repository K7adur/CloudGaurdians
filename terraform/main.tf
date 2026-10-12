
terraform {
  required_version = ">= 1.4.0"
}

resource "terraform_data" "cloudguardians_local_deployment" {
  triggers_replace = [
    filesha256("${path.module}/../Docker-compose.yml")
  ]

  provisioner "local-exec" {
    interpreter = ["powershell", "-NoProfile", "-Command"]
    command     = "docker compose -f '${path.module}/../Docker-compose.yml' up --build -d"
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["powershell", "-NoProfile", "-Command"]
    command     = "docker compose -f '${path.module}/../Docker-compose.yml' down"
  }
}

output "deployment_type" {
  value = "Local Docker-based disaster recovery simulation"
}

output "gateway_url" {
  value = "http://localhost:8080"
}

output "primary_url" {
  value = "http://localhost:5001"
}

output "secondary_url" {
  value = "http://localhost:5002"
}
