resource "aws_security_group" "alb_sg" {
  name        = "notas-alb-sg"
  description = "HTTP publico hacia el Application Load Balancer"
  vpc_id      = local.vpc_id

  ingress {
    description = "HTTP publico"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "api_sg" {
  name        = "notas-api-sg"
  description = "API solo recibe trafico desde el ALB"
  vpc_id      = local.vpc_id

  ingress {
    description     = "FastAPI desde ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  ingress {
    description = "SSH desde mi IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "backend_sg" {
  name        = "notas-backend-sg"
  description = "MongoDB y RabbitMQ para la API"
  vpc_id      = local.vpc_id

  ingress {
    description     = "RabbitMQ AMQP desde API"
    from_port       = 5672
    to_port         = 5672
    protocol        = "tcp"
    security_groups = [aws_security_group.api_sg.id]
  }

  ingress {
    description     = "MongoDB desde API"
    from_port       = 27017
    to_port         = 27017
    protocol        = "tcp"
    security_groups = [aws_security_group.api_sg.id]
  }

  ingress {
    description = "RabbitMQ management solo desde mi IP"
    from_port   = 15672
    to_port     = 15672
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  ingress {
    description = "SSH desde mi IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
