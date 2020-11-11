variable "vsphere_user" {
}

variable "vsphere_password" {
}

variable "vsphere_server" {
}

variable "dns_server" {
  default = "8.8.8.8"
}

variable "dc" {
  default     = "lab"
}

variable "cluster" {
  default     = "zoo"
}

variable "datastore" {
  default     = "minas-LUN-3"
}

variable "network" {
  default     = "pg-vmnetwork"
}
