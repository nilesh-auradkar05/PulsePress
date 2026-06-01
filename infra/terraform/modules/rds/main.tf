# Private PostgreSQL (RDS). Not publicly accessible; reachable only from the API
# service security group. The master password is managed by AWS in Secrets
# Manager (manage_master_user_password) so no credential is ever in Terraform
# state or committed to git.

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db-subnets"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds-sg"
  description = "Postgres access from the API service only."
  vpc_id      = var.vpc_id

  ingress {
    description     = "Postgres from the API service"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.source_security_group_id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-rds-sg" }
}

resource "aws_db_instance" "this" {
  identifier                  = "${var.name_prefix}-pg"
  engine                      = "postgres"
  engine_version              = var.engine_version
  instance_class              = var.instance_class
  allocated_storage           = var.allocated_storage
  db_name                     = "pulsepress"
  username                    = "pulsepress"
  manage_master_user_password = true
  db_subnet_group_name        = aws_db_subnet_group.this.name
  vpc_security_group_ids      = [aws_security_group.rds.id]
  publicly_accessible         = false
  storage_encrypted           = true
  skip_final_snapshot         = true
  deletion_protection         = false
  apply_immediately           = true
}
