#Name of folder to be created, also uniqueness value for disk, etc
variable "id" {
  default     = "lab"
}

variable "owner" {
  description = "Owner tag appropriately"
  default     = "lab_Owner"
}
#Number of controllers to deploy
variable "pod_count" {
  default     = "1"
}

variable "master_count" {
  description = "K8S Masters count per pod"
  default     = "1"
}

variable "server_count" {
  description = "K8S Workers count per pod"
  default     = "3"
}

variable "jumpbox" {
  type = map
  default = {
    cpu = 2
    memory = 4096
    disk = 20
    # The image must support user-data, https://cloud-images.ubuntu.com/bionic/current/
    template = "ubuntu-bionic-18.04-cloudimg-20200416"
  # mgmt_ip = ""
  # mgmt_mask = ""
  # default_gw = ""
  }
}

variable "server" {
  type = map
  default = {
    cpu = 2
    memory = 4096
    disk = 60
    # The image must support user-data, https://cloud-images.ubuntu.com/bionic/current/
    template = "ubuntu-bionic-18.04-cloudimg-20200416"
  # mgmt_ip = ""
  # mgmt_mask = ""
  # default_gw = ""
  }
}

# depends on the underlay lab environment, it can take longer than 2 minutes for VM to come up and get IP address by DHCP
variable "wait_for_guest_net_timeout" {
  default = "5"
}

variable "lab_admin_password" {
  default = "r00tpassw0rd"
}
