
import qrcode
import base64
from io import BytesIO


class QRService:

    @staticmethod
    def generate_qr(ticket_code: str):

        if not ticket_code:
            raise ValueError("Ticket code is required")

        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=4
        )

        qr.add_data(ticket_code)
        qr.make(fit=True)

        image = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        buffer = BytesIO()
        image.save(buffer, format="PNG")

        image_bytes = buffer.getvalue()

        encoded_image = base64.b64encode(
            image_bytes
        ).decode("utf-8")

        return {
            "ticket_code": ticket_code,
            "qr_code": encoded_image,
            "image_format": "PNG"
        }
