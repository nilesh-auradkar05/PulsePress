resource "aws_cloudwatch_event_bus" "this" {
  name = "${var.name_prefix}-events"
}

resource "aws_sqs_queue" "dead_letter" {
  name                      = "${var.name_prefix}-worker-dlq"
  message_retention_seconds = var.dead_letter_retention_seconds
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "event_delivery_dead_letter" {
  name                      = "${var.name_prefix}-eventbridge-dlq"
  message_retention_seconds = var.dead_letter_retention_seconds
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "worker" {
  name                       = "${var.name_prefix}-worker"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter.arn
    maxReceiveCount     = var.max_receive_count
  })
}

resource "aws_cloudwatch_event_rule" "worker_delivery" {
  name           = "${var.name_prefix}-worker-delivery"
  event_bus_name = aws_cloudwatch_event_bus.this.name
  event_pattern = jsonencode({
    source = ["pulsepress.api", "pulsepress.worker"]
    "detail-type" = [
      "subscription.created",
      "subscription.tier_changed",
      "subscription.canceled",
      "gift.sent",
      "ledger.transaction.recorded",
      "event.processing.failed",
    ]
  })
}

resource "aws_cloudwatch_event_target" "worker_queue" {
  rule           = aws_cloudwatch_event_rule.worker_delivery.name
  event_bus_name = aws_cloudwatch_event_bus.this.name
  arn            = aws_sqs_queue.worker.arn

  dead_letter_config {
    arn = aws_sqs_queue.event_delivery_dead_letter.arn
  }

  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = 24
  }
}

data "aws_iam_policy_document" "worker_queue" {
  statement {
    sid     = "AllowEventBridgeDelivery"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]
    resources = [
      aws_sqs_queue.worker.arn,
    ]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.worker_delivery.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "worker" {
  queue_url = aws_sqs_queue.worker.id
  policy    = data.aws_iam_policy_document.worker_queue.json
}

data "aws_iam_policy_document" "event_delivery_dead_letter" {
  statement {
    sid     = "AllowEventBridgeTargetFailureDelivery"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]
    resources = [
      aws_sqs_queue.event_delivery_dead_letter.arn,
    ]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.worker_delivery.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "event_delivery_dead_letter" {
  queue_url = aws_sqs_queue.event_delivery_dead_letter.id
  policy    = data.aws_iam_policy_document.event_delivery_dead_letter.json
}

resource "aws_s3_bucket" "receipts" {
  bucket_prefix = "${var.name_prefix}-receipts-"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "receipts" {
  bucket = aws_s3_bucket.receipts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "receipts" {
  bucket                  = aws_s3_bucket.receipts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "receipts" {
  bucket = aws_s3_bucket.receipts.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "receipts" {
  bucket = aws_s3_bucket.receipts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "receipts_bucket" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.receipts.arn,
      "${aws_s3_bucket.receipts.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "receipts" {
  bucket = aws_s3_bucket.receipts.id
  policy = data.aws_iam_policy_document.receipts_bucket.json
}
