# HRESULT Decode Reference

## Common Media Foundation / PlayReady HRESULTs

| HRESULT | Name | Meaning |
|---|---|---|
| `0x8004CD12` | `DRM_E_LICENSENOTFOUND` / hardware reset variant | Device/GPU context lost during DRM operation, or missing license |
| `0xC00D36B1` | `MF_E_SHUTDOWN` | MF object used after shutdown |
| `0xC00D7159` | `MF_E_UNEXPECTED` | Engine in invalid state |
| `0xC00D36D5` | `MF_E_NOT_FOUND` | Resource/key not found |
| `0x8007000E` | `E_OUTOFMEMORY` | Out of memory (often GPU memory after device loss) |
| `0xC00D6D6D` | `MF_E_UNSUPPORTED_SERVICE` | DRM/PMP service unavailable |
| `0x8004DA73` | PlayReady DRM error | License/key acquisition failure |
| `0x80004004` | `E_ABORT` | Operation aborted |
| `0x80004005` | `NS_ERROR_FAILURE` | General failure |
| `0xC00D3E85` | `MF_E_INVALIDSTREAMNUMBER` | Invalid stream |

## High-Bit Classification

For unknown codes, the high bits identify the category:

| Pattern | Category |
|---|---|
| `0x8007xxxx` | Win32 error wrapped in HRESULT — look up the low 16 bits as a Win32 error code |
| `0xC00Dxxxx` | Media Foundation error |
| `0x8004xxxx` | COM / DRM error |
| `0x8000xxxx` | Standard COM error |
