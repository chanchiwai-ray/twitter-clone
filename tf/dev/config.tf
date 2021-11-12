terraform {
  backend "s3" {
    bucket  = "intern-raychan"
    key     = "terraform.tfstate-mission-2"
    region  = "ap-northeast-1"
    encrypt = "true"
  }
}

provider "aws" {
  region = "ap-northeast-1"
  default_tags {
    tags = {
      Project = "raychan"
    }
  }
}
