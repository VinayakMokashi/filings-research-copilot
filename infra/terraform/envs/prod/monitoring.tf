# Alerts and a dashboard (ADR-0031). Four alert conditions: the database left running,
# server errors, dead letters, and the web UI unreachable. The budget's own emails come
# from the billing account (bootstrap).

resource "google_monitoring_notification_channel" "owner" {
  display_name = "Project owner"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
}

resource "google_monitoring_alert_policy" "database_left_running" {
  display_name          = "Demo database up for four hours"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.owner.id]

  conditions {
    display_name = "Cloud SQL instance facts is up"
    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND metric.type = \"cloudsql.googleapis.com/database/up\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.5
      duration        = "14400s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  documentation {
    content   = "The demo database has run for four hours. Unless a demo is still going, stop it: `uv run poe demo-down`. The nightly job stops it at 23:30 IST in any case."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "server_errors" {
  display_name          = "Server errors on a Cloud Run service"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.owner.id]

  conditions {
    display_name = "More than five 5xx responses in five minutes"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.service_name"]
      }
    }
  }

  documentation {
    content   = "A service is failing requests. Check its logs in Cloud Logging; roll back with the runbook if a deploy caused it."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "dead_letters" {
  display_name          = "Ingestion requests in the dead-letter queue"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.owner.id]

  conditions {
    display_name = "Undelivered messages in ingest-dead-letter"
    condition_threshold {
      filter          = "resource.type = \"pubsub_subscription\" AND resource.labels.subscription_id = \"ingest-dead-letter\" AND metric.type = \"pubsub.googleapis.com/subscription/num_undelivered_messages\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  documentation {
    content   = "An ingestion request failed five times. Read it from the ingest-dead-letter subscription, fix the cause, and publish it again."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_uptime_check_config" "ui" {
  display_name = "Web UI"
  timeout      = "30s"
  period       = "900s"

  http_check {
    path         = "/_stcore/health"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = local.host.ui
    }
  }
}

resource "google_monitoring_alert_policy" "ui_unreachable" {
  display_name          = "Web UI unreachable"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.owner.id]

  conditions {
    display_name = "The uptime check fails from more than one region"
    condition_threshold {
      filter          = "metric.type = \"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type = \"uptime_url\" AND metric.labels.check_id = \"${google_monitoring_uptime_check_config.ui.uptime_check_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "1800s"
      aggregations {
        alignment_period     = "1200s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.*"]
      }
    }
  }
}

resource "google_monitoring_dashboard" "copilot" {
  dashboard_json = jsonencode({
    displayName = "Filings Research Copilot"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width = 6, height = 4, xPos = 0, yPos = 0
          widget = {
            title = "Requests by service and response class"
            xyChart = {
              dataSets = [{
                plotType = "STACKED_BAR"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_count\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_SUM"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["resource.label.service_name", "metric.label.response_code_class"]
                    }
                  }
                }
              }]
            }
          }
        },
        {
          width = 6, height = 4, xPos = 6, yPos = 0
          widget = {
            title = "Request latency, 95th percentile"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_latencies\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_PERCENTILE_95"
                      crossSeriesReducer = "REDUCE_MAX"
                      groupByFields      = ["resource.label.service_name"]
                    }
                  }
                }
              }]
            }
          }
        },
        {
          width = 6, height = 4, xPos = 0, yPos = 4
          widget = {
            title = "Instances by service"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/container/instance_count\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_MAX"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["resource.label.service_name"]
                    }
                  }
                }
              }]
            }
          }
        },
        {
          width = 6, height = 4, xPos = 6, yPos = 4
          widget = {
            title = "Memory used, 99th percentile"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/container/memory/utilizations\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_PERCENTILE_99"
                      crossSeriesReducer = "REDUCE_MAX"
                      groupByFields      = ["resource.label.service_name"]
                    }
                  }
                }
              }]
            }
          }
        },
        {
          width = 6, height = 4, xPos = 0, yPos = 8
          widget = {
            title = "Demo database up"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type = \"cloudsql_database\" AND metric.type = \"cloudsql.googleapis.com/database/up\""
                    aggregation = {
                      alignmentPeriod  = "300s"
                      perSeriesAligner = "ALIGN_MAX"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          width = 6, height = 4, xPos = 6, yPos = 8
          widget = {
            title = "Ingestion: undelivered and dead-lettered messages"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type = \"pubsub_subscription\" AND metric.type = \"pubsub.googleapis.com/subscription/num_undelivered_messages\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_MAX"
                      crossSeriesReducer = "REDUCE_MAX"
                      groupByFields      = ["resource.label.subscription_id"]
                    }
                  }
                }
              }]
            }
          }
        },
      ]
    }
  })
}
