"""
Centralized Azure AD authentication for Fabric and Power BI deployment.

Supports three authentication flows:
1. **Service Principal** — client_id + client_secret + tenant_id
2. **Managed Identity** — system-assigned or user-assigned
3. **Interactive browser** — for local development

Provides token caching and automatic refresh.

Requires ``azure-identity`` package (optional dependency).
"""

import logging
import time

logger = logging.getLogger(__name__)

_FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
_PBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

# In-memory token cache
_token_cache = {}


# ── Public API ───────────────────────────────────────────────────


def get_token(scope=None, *, credential=None,
              tenant_id=None, client_id=None, client_secret=None,
              managed_identity=False, user_assigned_id=None):
    """Obtain a bearer token for the specified scope.

    Tries flows in order:
    1. Provided ``credential`` object (any ``azure.identity`` credential).
    2. Service Principal if ``client_id`` and ``client_secret`` supplied.
    3. Managed Identity if ``managed_identity=True``.
    4. Interactive browser as fallback (only if ``azure-identity`` available).

    Returns:
        Access token string.

    Raises:
        RuntimeError: If no valid credential flow succeeds.
    """
    scope = scope or _FABRIC_SCOPE

    # Check cache
    cached = _token_cache.get(scope)
    if cached and cached["expires_on"] > time.time() + 60:
        return cached["token"]

    token = None

    # 1. Explicit credential
    if credential is not None:
        token = _get_token_from_credential(credential, scope)

    # 2. Service Principal
    if token is None and client_id and client_secret and tenant_id:
        token = _get_service_principal_token(
            tenant_id, client_id, client_secret, scope,
        )

    # 3. Managed Identity
    if token is None and managed_identity:
        token = _get_managed_identity_token(scope, user_assigned_id)

    # 4. Interactive browser
    if token is None:
        token = _get_interactive_token(scope)

    if token is None:
        raise RuntimeError(
            "Failed to obtain access token.  Provide a credential, "
            "service principal details, enable managed identity, "
            "or install azure-identity for interactive auth."
        )

    return token


def get_fabric_token(**kwargs):
    """Shortcut for Fabric API scope."""
    return get_token(_FABRIC_SCOPE, **kwargs)


def get_pbi_token(**kwargs):
    """Shortcut for Power BI API scope."""
    return get_token(_PBI_SCOPE, **kwargs)


def clear_cache():
    """Clear the in-memory token cache."""
    _token_cache.clear()


# ── Token acquisition methods ────────────────────────────────────


def _get_token_from_credential(credential, scope):
    """Use an azure.identity credential object."""
    try:
        result = credential.get_token(scope)
        _cache_token(scope, result.token, result.expires_on)
        logger.info("Obtained token via provided credential")
        return result.token
    except Exception as exc:
        logger.warning("Credential token acquisition failed: %s", exc)
        return None


def _get_service_principal_token(tenant_id, client_id, client_secret, scope):
    """Use ClientSecretCredential for service principal auth."""
    try:
        from azure.identity import ClientSecretCredential
        cred = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        result = cred.get_token(scope)
        _cache_token(scope, result.token, result.expires_on)
        logger.info("Obtained token via Service Principal (client_id=%s)", client_id)
        return result.token
    except ImportError:
        logger.warning("azure-identity not installed — cannot use Service Principal")
        return None
    except Exception as exc:
        logger.warning("Service Principal auth failed: %s", exc)
        return None


def _get_managed_identity_token(scope, user_assigned_id=None):
    """Use ManagedIdentityCredential."""
    try:
        from azure.identity import ManagedIdentityCredential
        kwargs = {}
        if user_assigned_id:
            kwargs["client_id"] = user_assigned_id
        cred = ManagedIdentityCredential(**kwargs)
        result = cred.get_token(scope)
        _cache_token(scope, result.token, result.expires_on)
        logger.info("Obtained token via Managed Identity")
        return result.token
    except ImportError:
        logger.warning("azure-identity not installed — cannot use Managed Identity")
        return None
    except Exception as exc:
        logger.warning("Managed Identity auth failed: %s", exc)
        return None


def _get_interactive_token(scope):
    """Use InteractiveBrowserCredential for local dev."""
    try:
        from azure.identity import InteractiveBrowserCredential
        cred = InteractiveBrowserCredential()
        result = cred.get_token(scope)
        _cache_token(scope, result.token, result.expires_on)
        logger.info("Obtained token via interactive browser flow")
        return result.token
    except ImportError:
        logger.debug("azure-identity not installed — skipping interactive auth")
        return None
    except Exception as exc:
        logger.warning("Interactive auth failed: %s", exc)
        return None


# ── Cache management ─────────────────────────────────────────────


def _cache_token(scope, token, expires_on):
    """Store a token in the in-memory cache."""
    _token_cache[scope] = {"token": token, "expires_on": expires_on}
