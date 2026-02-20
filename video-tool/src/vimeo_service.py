"""Vimeo API operaties: upload, metadata, status."""

import vimeo


PRIVACY_OPTIONS = {
    "Alleen via privelink": "unlisted",
    "Iedereen": "anybody",
    "Wachtwoord": "password",
    "Niemand (verborgen)": "nobody",
}


class VimeoService:
    """Vimeo API client voor video-upload en -beheer."""

    def __init__(self, access_token: str):
        self.client = vimeo.VimeoClient(token=access_token)

    def check_connection(self) -> dict | None:
        """Test API-verbinding en retourneer accountinfo.

        Returns dict met name en account_type, of None bij fout.
        """
        try:
            response = self.client.get("/me?fields=name,account")
            if response.status_code == 200:
                data = response.json()
                return {
                    "name": data.get("name", "Onbekend"),
                    "account_type": data.get("account", "unknown"),
                }
        except Exception:
            pass
        return None

    def get_upload_quota(self) -> dict | None:
        """Haal upload-quota op.

        Returns dict met free_space (bytes) en max_size (bytes per video).
        """
        try:
            response = self.client.get("/me?fields=upload_quota")
            if response.status_code == 200:
                quota = response.json().get("upload_quota", {})
                space = quota.get("space", {})
                return {
                    "free_space": space.get("free", 0),
                    "max_size": space.get("max", 0),
                }
        except Exception:
            pass
        return None

    def list_folders(self) -> list[dict]:
        """Haal alle mappen/projecten op uit het Vimeo-account.

        Returns lijst van dicts met: uri, name
        """
        folders = []
        try:
            response = self.client.get(
                "/me/projects?fields=uri,name&per_page=100&sort=name"
            )
            if response.status_code == 200:
                for item in response.json().get("data", []):
                    folders.append({
                        "uri": item["uri"],
                        "name": item.get("name", "Naamloos"),
                    })
        except Exception:
            pass
        return folders

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str = "",
        privacy: str = "unlisted",
        password: str = "",
        folder_uri: str = "",
    ) -> dict | None:
        """Upload video naar Vimeo.

        Gebruikt twee-staps aanpak: eerst uploaden, dan metadata instellen.
        Dit voorkomt 'invalid parameter' fouten bij de upload.

        Args:
            file_path: Pad naar het MP4-bestand
            title: Videotitel
            description: Beschrijving
            privacy: Een van 'unlisted', 'anybody', 'password', 'nobody'
            password: Wachtwoord (alleen als privacy='password')
            folder_uri: Vimeo folder URI (bv. '/users/123/projects/456'), of leeg

        Returns dict met uri en link, of None bij fout.
        """
        try:
            # Stap 1: Upload bestand met minimale data
            upload_data = {"name": title}
            if folder_uri:
                upload_data["folder_uri"] = folder_uri
            video_uri = self.client.upload(file_path, data=upload_data)

            # Stap 2: Metadata instellen via PATCH
            patch_data = {
                "description": description,
                "privacy": {"view": privacy},
            }
            if privacy == "password" and password:
                patch_data["privacy"]["password"] = password

            self.client.patch(video_uri, data=patch_data)

            # Stap 3: Haal de link op
            response = self.client.get(
                f"{video_uri}?fields=link,transcode.status,name"
            )
            if response.status_code == 200:
                video_data = response.json()
                return {
                    "uri": video_uri,
                    "link": video_data.get("link", ""),
                    "name": video_data.get("name", title),
                    "transcode_status": video_data.get("transcode", {}).get(
                        "status", "unknown"
                    ),
                }
        except Exception as e:
            raise RuntimeError(f"Vimeo upload mislukt: {e}") from e

        return None

    def get_transcode_status(self, video_uri: str) -> str:
        """Controleer video transcodeer-status.

        Returns: 'in_progress', 'complete', of 'error'
        """
        try:
            response = self.client.get(f"{video_uri}?fields=transcode.status")
            if response.status_code == 200:
                return (
                    response.json().get("transcode", {}).get("status", "unknown")
                )
        except Exception:
            pass
        return "unknown"
