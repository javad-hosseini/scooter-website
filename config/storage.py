from whitenoise.storage import CompressedManifestStaticFilesStorage


class LenientWhiteNoiseStorage(CompressedManifestStaticFilesStorage):
    """
    Prevent collectstatic from crashing when a third-party stylesheet
    references a missing sourcemap (.map) or asset.
    """
    manifest_strict = False
