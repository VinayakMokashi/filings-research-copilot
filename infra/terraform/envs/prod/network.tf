# A small VPC whose only job is the database's private address (ADR-0031): a stopped
# Cloud SQL instance with a public IPv4 address pays $0.01 an hour for it.

resource "google_compute_network" "copilot" {
  name                    = "copilot"
  auto_create_subnetworks = false
}

# Cloud Run's Direct VPC egress takes its addresses from this subnet.
resource "google_compute_subnetwork" "run" {
  name                     = "run-${var.region}"
  network                  = google_compute_network.copilot.id
  region                   = var.region
  ip_cidr_range            = "10.10.0.0/24"
  private_ip_google_access = true
}

# Private services access: Google's network for Cloud SQL, peered with this one.
resource "google_compute_global_address" "services" {
  name          = "google-services"
  network       = google_compute_network.copilot.id
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  address       = "10.20.0.0"
  prefix_length = 20
}

resource "google_service_networking_connection" "services" {
  network                 = google_compute_network.copilot.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.services.name]
}
