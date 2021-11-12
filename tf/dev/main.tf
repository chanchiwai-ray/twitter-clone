# Declare the data source
data "aws_availability_zones" "available" {}

resource "aws_ecr_repository" "twitter_repo" {
  name = var.ecr_name

  image_scanning_configuration {
    scan_on_push = true
  }
}

#
# ECS cluster
#

resource "aws_ecs_cluster" "web_app_cluster" {
  name = "${var.resource_prefix}-${var.ecs_name}"
}

#
# VPC 
#

module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "${var.resource_prefix}-${var.vpc_name}"
  cidr = var.vpc_cidr

  azs             = data.aws_availability_zones.available.names
  public_subnets  = var.vpc_public_subnets
  private_subnets = var.vpc_private_subnets

  elasticache_subnets             = var.vpc_elastic_cache_subnets
  create_elasticache_subnet_group = true
  elasticache_subnet_tags = {
    name : "ec_subnet"
  }
}

#
# Security group for Load balancer
#

module "lb_security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "4.3.0"

  name        = "${var.resource_prefix}-${var.lb_sg_name}"
  description = "Security group for twitters load balancer"
  vpc_id      = module.vpc.vpc_id

  egress_cidr_blocks = var.lb_egress_cidr_blocks
  egress_rules       = var.lb_egress_rules

  ingress_cidr_blocks = var.lb_ingress_cidr_blocks
  ingress_rules       = var.lb_ingress_rules
}


#
# Security group for ECS cluster
#

module "ecs_security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "4.3.0"

  name        = "${var.resource_prefix}-${var.ecs_sg_name}"
  description = "Security group for twitters ECS tasks"
  vpc_id      = module.vpc.vpc_id

  egress_cidr_blocks = var.ecs_egress_cidr_blocks
  egress_rules       = var.ecs_egress_rules

  ingress_with_source_security_group_id = [{
    source_security_group_id : module.lb_security_group.security_group_id,
    rule : var.ecs_ingress_rule
  }]
}


#
# Security group for elasticache
#

module "ec_security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "4.3.0"

  name        = "${var.resource_prefix}-${var.ec_sg_name}"
  description = "Security group for twitters elasticache"
  vpc_id      = module.vpc.vpc_id

  egress_cidr_blocks = var.ec_egress_cidr_blocks
  egress_rules       = var.ec_egress_rules

  ingress_with_source_security_group_id = [{
    source_security_group_id : module.ecs_security_group.security_group_id,
    rule : var.ec_ingress_rule
  }]
}

#
# CloudWatch Log
#

resource "aws_cloudwatch_log_group" "web_app_cloudwatch_log" {
  name = "${var.resource_prefix}/${var.cloudwatch_name}"
}

#
# Task Definition
#

resource "aws_ecs_task_definition" "web_app_task" {
  family = "${var.resource_prefix}-twitter"

  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = "arn:aws:iam::741641693274:role/intern-devops-ecs"
  task_role_arn            = "arn:aws:iam::741641693274:role/intern-devops-ecs"
  network_mode             = "awsvpc"

  container_definitions = <<DEFINITION
[
  {
    "name": "${var.container_name}",
    "image": "${aws_ecr_repository.twitter_repo.repository_url}:${var.image_tag}",
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-region": "${var.resource_region}",
        "awslogs-group": "${aws_cloudwatch_log_group.web_app_cloudwatch_log.name}",
        "awslogs-stream-prefix": "${var.awslogs_stream_prefix}"
      }
    },
    "portMappings": [
      {
        "containerPort": ${var.container_port},
        "hostPort": ${var.container_port}
      }
    ],
    "environment": [
      {
        "name": "OAUTHLIB_INSECURE_TRANSPORT",
        "value": "${var.oauthlib_insecure_transport}"
      },
      {
        "name": "OAUTH_REDIRECT_URL",
        "value": "${var.oauth_redirect_url}"
      },
      {
        "name": "S3_BUCKET_NAME",
        "value": "${var.s3_bucket_name}"
      },
      {
        "name": "REDIS_PROD_HOST",
        "value": "${aws_elasticache_cluster.redis_ec_cluster.cache_nodes[0].address}"
      },
      {
        "name": "REDIS_PROD_PORT",
        "value": "${aws_elasticache_cluster.redis_ec_cluster.cache_nodes[0].port}"
      },
      {
        "name": "${split("/", aws_ssm_parameter.google_client_id.name)[2]}",
        "value": "${aws_ssm_parameter.google_client_id.value}"
      },
      {
        "name": "${split("/", aws_ssm_parameter.oauth_client_secret_path.name)[2]}",
        "value": "${aws_ssm_parameter.oauth_client_secret_path.value}"
      },
      {
        "name": "${split("/", aws_ssm_parameter.app_secret_key.name)[2]}",
        "value": "${aws_ssm_parameter.app_secret_key.value}"
      }
    ]
  }
] 
DEFINITION
}

#
# Load balancer
#

module "alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "~> 6.0"

  name = "${var.resource_prefix}-web-app-lb"

  load_balancer_type = "application"

  vpc_id          = module.vpc.vpc_id
  subnets         = module.vpc.public_subnets
  security_groups = [module.lb_security_group.security_group_id]

  target_groups = [
    {
      name             = "${var.resource_prefix}-tg"
      backend_protocol = "HTTP"
      backend_port     = 80
      target_type      = "ip"
    }
  ]

  https_listeners = [
    {
      port               = 443
      protocol           = "HTTPS"
      certificate_arn    = module.acm.acm_certificate_arn
      target_group_index = 0
    }
  ]

  http_tcp_listeners = [
    {
      port        = 80
      protocol    = "HTTP"
      action_type = "redirect"
      redirect = {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  ]
}

#
# ECS service
#

resource "aws_ecs_service" "web_app_service" {
  name                               = "${var.resource_prefix}-web-app-service"
  cluster                            = aws_ecs_cluster.web_app_cluster.id
  task_definition                    = aws_ecs_task_definition.web_app_task.arn
  desired_count                      = 2
  launch_type                        = "FARGATE"
  deployment_maximum_percent         = 100
  deployment_minimum_healthy_percent = 50
  force_new_deployment               = true
  network_configuration {
    subnets          = module.vpc.public_subnets
    security_groups  = [module.ecs_security_group.security_group_id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = module.alb.target_group_arns[0]
    container_name   = var.container_name
    container_port   = var.container_port
  }
}

#
# Redis Elasticache Cluster
#

resource "aws_elasticache_cluster" "redis_ec_cluster" {
  cluster_id           = "${var.resource_prefix}-${var.elasticache_cluster_id}"
  engine               = "redis"
  node_type            = "cache.t2.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis6.x"
  engine_version       = "6.x"
  port                 = 6379
  security_group_ids   = [module.ec_security_group.security_group_id]
  subnet_group_name    = module.vpc.elasticache_subnet_group_name
  apply_immediately    = true
}

#
# ACM and Route53
#

module "acm" {
  source  = "terraform-aws-modules/acm/aws"
  version = "3.2.0"

  domain_name = "${var.subdomain_name}.${var.domain_name}"
  zone_id     = var.route53_hosted_zone_id
}

#
# Alias Route53 record
#

resource "aws_route53_record" "frontend" {
  zone_id = var.route53_hosted_zone_id
  name    = "${var.subdomain_name}.${var.domain_name}"
  type    = "A"

  alias {
    name                   = module.alb.lb_dns_name
    zone_id                = module.alb.lb_zone_id
    evaluate_target_health = true
  }
}

#
# secrets (parameter store)
#

resource "aws_ssm_parameter" "google_client_id" {
  name  = "/${var.resource_prefix}/GOOGLE_CLIENT_ID"
  type  = "SecureString"
  value = var.google_client_id
}

resource "aws_ssm_parameter" "oauth_client_secret_path" {
  name  = "/${var.resource_prefix}/OAUTH_CLIENT_SECRET_PATH"
  type  = "SecureString"
  value = var.oauth_client_secret_path
}

resource "aws_ssm_parameter" "app_secret_key" {
  name  = "/${var.resource_prefix}/APP_SECRET_KEY"
  type  = "SecureString"
  value = var.app_secret_key
}
