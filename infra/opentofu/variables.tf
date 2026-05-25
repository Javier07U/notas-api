variable "aws_region" {
  description = "Región del Learner Lab. Usa normalmente us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "VPC donde se desplegará. Déjalo vacío para usar la default VPC."
  type        = string
  default     = ""
}

variable "subnet_ids" {
  description = "Subnets públicas para el ALB y las EC2. Déjalo vacío para usar subnets default."
  type        = list(string)
  default     = []
}

variable "instance_type" {
  description = "Tipo de instancia permitido por AWS Academy."
  type        = string
  default     = "t2.micro"
}

variable "key_name" {
  description = "Nombre del key pair EC2. Opcional, pero recomendado para entrar por SSH."
  type        = string
  default     = ""
}

variable "my_ip_cidr" {
  description = "Tu IP pública en formato x.x.x.x/32 para SSH y RabbitMQ UI."
  type        = string
}
