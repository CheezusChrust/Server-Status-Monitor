from iso3166 import countries
import ipaddress


def validate_ip(ip: str):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def validate_port(port: int):
    if port > 65535 or port < 1:
        return False
    return True


def validate_country(country: str):
    if len(country) != 2:
        return False
    try:
        countries.get(country)
    except KeyError:
        return False

    return True
