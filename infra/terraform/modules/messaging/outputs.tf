output "event_bus_name" {
  value = aws_cloudwatch_event_bus.this.name
}

output "event_bus_arn" {
  value = aws_cloudwatch_event_bus.this.arn
}

output "worker_queue_url" {
  value = aws_sqs_queue.worker.id
}

output "worker_queue_arn" {
  value = aws_sqs_queue.worker.arn
}

output "dead_letter_queue_url" {
  value = aws_sqs_queue.dead_letter.id
}

output "dead_letter_queue_arn" {
  value = aws_sqs_queue.dead_letter.arn
}

output "event_delivery_dead_letter_queue_url" {
  value = aws_sqs_queue.event_delivery_dead_letter.id
}

output "receipt_bucket_name" {
  value = aws_s3_bucket.receipts.id
}

output "receipt_bucket_arn" {
  value = aws_s3_bucket.receipts.arn
}
