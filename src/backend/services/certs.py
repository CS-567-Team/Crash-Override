"""Self-signed HTTPS certificate so the headset can use WebXR over Wi-Fi.

Browsers only allow VR on https:// pages (or localhost). The certificate is made once per
laptop address and kept in runtime/certs; the headset shows a warning the first time,
which is expected for a certificate you made yourself."""

import datetime
import ipaddress
import socket
from pathlib import Path


def lan_address() -> str:
    """This machine's address on the local network (no packets are sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("10.255.255.255", 1))
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def ensure_certificate(directory: Path, address: str) -> tuple[Path, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    directory.mkdir(parents=True, exist_ok=True)
    cert_path, key_path, marker = directory / "cert.pem", directory / "key.pem", directory / "address.txt"
    if cert_path.is_file() and key_path.is_file() and marker.is_file() and marker.read_text() == address:
        return cert_path, key_path

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Crash Override local server")])
    now = datetime.datetime.now(datetime.timezone.utc)
    names = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    if address != "127.0.0.1":
        names.append(x509.IPAddress(ipaddress.ip_address(address)))
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(names), critical=False)
            .sign(key, hashes.SHA256()))

    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    marker.write_text(address)
    return cert_path, key_path
