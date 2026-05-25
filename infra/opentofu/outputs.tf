output "alb_dns_name" {
  description = "URL pública de la API detrás del ALB"
  value       = "http://${aws_lb.api_alb.dns_name}"
}

output "backend_private_ip" {
  description = "IP privada de backend para MongoDB/RabbitMQ/Worker"
  value       = aws_instance.backend.private_ip
}

output "rabbitmq_management_url" {
  description = "UI de RabbitMQ. Usuario admin, contraseña password123."
  value       = "http://${aws_instance.backend.public_ip}:15672"
}

output "api_instance_public_ips" {
  value = aws_instance.api[*].public_ip
}
