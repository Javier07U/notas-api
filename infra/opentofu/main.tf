data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

locals {
  vpc_id     = var.vpc_id != "" ? var.vpc_id : data.aws_vpc.default.id
  subnet_ids = length(var.subnet_ids) > 0 ? var.subnet_ids : slice(data.aws_subnets.default.ids, 0, 2)
}

resource "aws_instance" "backend" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  key_name               = var.key_name != "" ? var.key_name : null
  subnet_id              = local.subnet_ids[0]
  vpc_security_group_ids = [aws_security_group.backend_sg.id]
  user_data              = file("${path.module}/user_data_backend.sh")

  tags = {
    Name = "notas-backend-mongo-rabbit-worker"
  }
}

resource "aws_instance" "api" {
  count                  = 2
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  key_name               = var.key_name != "" ? var.key_name : null
  subnet_id              = local.subnet_ids[count.index]
  vpc_security_group_ids = [aws_security_group.api_sg.id]
  user_data = templatefile("${path.module}/user_data_api.sh.tftpl", {
    backend_private_ip = aws_instance.backend.private_ip
  })

  tags = {
    Name = "notas-api-${count.index + 1}"
  }
}

resource "aws_lb_target_group" "api_tg" {
  name     = "notas-api-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = local.vpc_id

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_target_group_attachment" "api_attachment" {
  count            = 2
  target_group_arn = aws_lb_target_group.api_tg.arn
  target_id        = aws_instance.api[count.index].id
  port             = 8000
}

resource "aws_lb" "api_alb" {
  name               = "notas-api-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = local.subnet_ids
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api_alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_tg.arn
  }
}
