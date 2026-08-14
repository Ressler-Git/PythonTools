from .hash_tool import create_hash_frame


def create_frame(parent):
    return create_hash_frame(parent, algorithm="md5", display_name="MD5")
