variable "ENV" {
  type = string
  description = "The prefix which should be used for all resources in this environment. Make it unique, like ksultanau."
}

variable "LOCATION" {
  type = string
  description = "The Azure Region in which all resources in this example should be created."
  default = "westeurope"
}

variable "BDCC_REGION" {
  type = string
  description = "The BDCC Region for billing."
  default = "global"
}

variable "STORAGE_ACCOUNT_REPLICATION_TYPE" {
  type = string
  description = "Storage Account replication type."
  default = "LRS"
}

variable "IP_RULES" {
  type = map(string)
  description = "Map of IP addresses permitted to access"
  default = {
    "epam-vpn-ru-0" = "185.44.13.36"
    "epam-vpn-eu-0" = "195.56.119.209"
    "epam-vpn-by-0" = "213.184.231.20"
    "epam-vpn-by-1" = "86.57.255.94"
  }
}
#
variable "CLIENT_ID" {

  type = string

  default = "48913c7f-d957-45f7-b75e-a94c27726985"

}


variable "CLIENT_SECRET" {

  type = string

  default = "P1h8Q~hKbVKUm4OCLUlRNeZjfQM4g3wL5EDDNbo2"

}


variable "SUBSCRIPTION_ID" {

  type = string

  default = "505382ea-f10e-4af8-99ba-db63736fe153"

}


variable "TENENT_ID" {

  type = string

  default = "b41b72d0-4e9f-4c26-8a69-f949f367c91d"

}
