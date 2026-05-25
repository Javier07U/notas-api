# Despliegue AWS Academy con OpenTofu

Arquitectura:

- 1 Application Load Balancer público en puerto 80.
- 2 EC2 con FastAPI en Docker, escuchando en puerto 8000.
- 1 EC2 backend con MongoDB, RabbitMQ y worker usando Docker Compose.
- El ALB revisa `/health` en cada API.
- La API envía POST, PUT y DELETE a RabbitMQ; el worker guarda/actualiza/borra en MongoDB.

## 1. Preparar AWS Academy

1. Entra a AWS Academy Learner Lab.
2. Pulsa **Start Lab**.
3. Abre **AWS Details** y copia las credenciales temporales.
4. Configura la terminal donde usarás OpenTofu:

```bash
aws configure
```

Usa `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` y región `us-east-1`.
Si usas archivo manual, guarda las credenciales en `~/.aws/credentials`, incluyendo `aws_session_token`.

Prueba:

```bash
aws sts get-caller-identity
aws ec2 describe-vpcs --region us-east-1
```

## 2. Preparar variables

```bash
cd infra/opentofu
cp terraform.tfvars.example terraform.tfvars
```

Edita `terraform.tfvars`:

```hcl
aws_region   = "us-east-1"
instance_type = "t2.micro"
key_name     = "nombre-de-tu-keypair"
my_ip_cidr   = "x.x.x.x/32"
```

Para obtener tu IP:

```bash
curl https://checkip.amazonaws.com
```

## 3. Crear infraestructura

```bash
tofu init
tofu fmt
tofu validate
tofu plan
tofu apply
```

Acepta con `yes`.

## 4. Esperar el arranque

El user data instala Docker, crea contenedores y arranca la API. Espera entre 4 y 8 minutos.

Ver outputs:

```bash
tofu output
```

Prueba salud:

```bash
curl $(tofu output -raw alb_dns_name)/health
```

## 5. Probar API

Crear nota:

```bash
API=$(tofu output -raw alb_dns_name)

curl -X POST "$API/notas" \
  -H "Content-Type: application/json" \
  -d '{"estudiante":"Ana Perez","materia":"Matematicas","calificacion":4.7,"fecha":"2026-05-24"}'
```

Copia el `taskId` y consulta:

```bash
curl "$API/tasks/TASK_ID"
```

Listar notas:

```bash
curl "$API/notas"
```

Actualizar nota:

```bash
curl -X PUT "$API/notas/NOTA_ID" \
  -H "Content-Type: application/json" \
  -d '{"calificacion":4.9}'
```

Borrar nota:

```bash
curl -X DELETE "$API/notas/NOTA_ID"
```

## 6. Entrar a RabbitMQ

```bash
tofu output -raw rabbitmq_management_url
```

Usuario: `admin`
Contraseña: `password123`

## 7. Debug

En una API EC2:

```bash
sudo tail -n 100 /var/log/notas-api-user-data.log
sudo docker ps
sudo docker logs notas-api
```

En backend EC2:

```bash
sudo tail -n 100 /var/log/notas-backend-user-data.log
cd /opt/notas-backend
sudo docker compose ps
sudo docker compose logs worker
```

## 8. Borrar todo al terminar

Muy importante en AWS Academy:

```bash
tofu destroy
```
