# Note: there are some placeholder variables (they are default to 'placeholder') that must be set, otherwise it won't work.


variable "resource_prefix" {
  default = "tclone-intern-raychan"
}

variable "resource_region" {
  default = "ap-northeast-1"
}

#
# ECR 
#

variable "ecr_name" {
  default = "tclone-intern-raychan-twitter"
}

variable "image_tag" {
  default = "latest"
}

#
# ECS 
#

variable "ecs_name" {
  default = "twitter-cluster"
}

#
# VPC
#

variable "vpc_name" {
  default = "twitter-vpc"
}

variable "vpc_cidr" {
  default = "192.168.0.0/24"
}

variable "vpc_public_subnets" {
  default = ["192.168.0.64/28", "192.168.0.80/28"]
}

variable "vpc_private_subnets" {
  default = []
}

variable "vpc_elastic_cache_subnets" {
  default = ["192.168.0.16/28"]
}

#
# Security Group (load balancer)
#

variable "lb_sg_name" {
  default = "load-balancer-sg"
}

variable "lb_egress_cidr_blocks" {
  default = ["0.0.0.0/0"]
}

variable "lb_egress_rules" {
  default = ["all-all"]
}

variable "lb_ingress_cidr_blocks" {
  default = ["210.253.197.196/32", "210.253.209.177/32", "118.238.221.230/32", "54.249.20.115/32", "150.249.192.7/32", "150.249.202.244/32", "150.249.202.245/32", "150.249.202.253/32", "0.0.0.0/0"]
}

variable "lb_ingress_rules" {
  default = ["http-80-tcp", "https-443-tcp"]
}

#
# Security Group (ecs tasks)
#

variable "ecs_sg_name" {
  default = "ecs-sg"
}

variable "ecs_egress_cidr_blocks" {
  default = ["0.0.0.0/0"]
}

variable "ecs_egress_rules" {
  default = ["all-all"]
}

variable "ecs_ingress_rule" {
  default = "http-80-tcp"
}

#
# Security Group (elastic cache)
#

variable "ec_sg_name" {
  default = "ec-sg"
}

variable "ec_egress_cidr_blocks" {
  default = ["0.0.0.0/0"]
}

variable "ec_egress_rules" {
  default = ["all-all"]
}

variable "ec_ingress_rule" {
  default = "redis-tcp"
}


#
# Cloud Watch Log
#

variable "cloudwatch_name" {
  default = "twitter-dev"
}

variable "awslogs_stream_prefix" {
  default = "twitter-log"
}


#
# Elasticache Cluster
#

variable "elasticache_cluster_id" {
  default = "ec-redis"
}


#
# Environments or secerts for images
#

variable "google_client_id" {
  default = "placeholder"
  type    = string
}

variable "oauth_client_secret_path" {
  default = "placeholder"
  type    = string
}

variable "app_secret_key" {
  default = "placeholder"
  type    = string
}

variable "oauthlib_insecure_transport" {
  default = "placeholder"
  type    = string
}

variable "oauth_redirect_url" {
  default = "placeholder"
  type    = string
}

variable "s3_bucket_name" {
  default = "placeholder"
  type    = string
}

#
# Route53 
#

variable "route53_hosted_zone_id" {
  default = "placeholder"
  type    = string
}

variable "domain_name" {
  default = "intern.aws.prd.demodesu.com"
}

variable "subdomain_name" {
  default = "raychan"
}

#
# Container
#

variable "container_name" {
  default = "twitter"
}

variable "container_port" {
  type    = number
  default = 80
}