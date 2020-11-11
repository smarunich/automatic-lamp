# Outputs for Terraform

output "jumpbox" {
  value = vsphere_virtual_machine.jumpbox.default_ip_address
}

output "masters" {
  value = vsphere_virtual_machine.master.*.default_ip_address
}
