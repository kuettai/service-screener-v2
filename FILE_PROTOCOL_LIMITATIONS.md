# File:// Protocol Limitations

This document describes the limitations and workarounds when using Service Screener reports with the `file://` protocol (opening HTML files directly in a browser).

## Overview

The Cloudscape UI is designed to work with the `file://` protocol, allowing you to open the HTML report directly from your filesystem without needing a web server. However, there are some browser security restrictions to be aware of.

## Why File:// Protocol?

**Advantages:**
- ✅ No web server required
- ✅ Works completely offline
- ✅ Easy to distribute (single HTML file)
- ✅ No network requests
- ✅ Secure (no external dependencies)

**Use Cases:**
- Opening reports on local machine
- Distributing reports via email/file share
- Viewing reports in air-gapped environments
- Quick ad-hoc analysis

## Browser Support

All major browsers support opening local HTML files:

| Browser | Support | Notes |
|---------|---------|-------|
| **Chrome** | ✅ Full | Best support, recommended |
| **Firefox** | ✅ Full | Excellent support |
| **Safari** | ✅ Full | Works well on macOS |
| **Edge** | ✅ Full | Chromium-based, same as Chrome |

## Known Limitations

### 1. No AJAX/Fetch Requests

**Limitation:** Browsers block AJAX/fetch requests from `file://` URLs for security.

**Impact:** ❌ None - The Cloudscape UI doesn't make any network requests. All data is embedded in the HTML file.

**Workaround:** Not needed.

### 2. Hash-Based Routing Required

**Limitation:** Traditional routing (e.g., `/service/s3`) doesn't work with `file://`.

**Impact:** ✅ Handled - We use hash-based routing (e.g., `#/service/s3`).

**Example URLs:**
```
file:///path/to/index.html#/
file:///path/to/index.html#/service/s3
file:///path/to/index.html#/framework/MSR
```

**Workaround:** Not needed - already implemented.

### 3. Local Storage Restrictions

**Limitation:** Some browsers restrict local storage access from `file://` URLs.

**Impact:** ❌ None - The Cloudscape UI doesn't use local storage.

**Workaround:** Not needed.

### 4. Cookies Not Available

**Limitation:** Cookies don't work with `file://` protocol.

**Impact:** ❌ None - The Cloudscape UI doesn't use cookies.

**Workaround:** Not needed.

### 5. Service Workers Not Supported

**Limitation:** Service workers can't be registered from `file://` URLs.

**Impact:** ❌ None - The Cloudscape UI doesn't use service workers.

**Workaround:** Not needed.

### 6. Web Workers Restrictions

**Limitation:** Web workers have limited functionality with `file://`.

**Impact:** ❌ None - The Cloudscape UI doesn't use web workers.

**Workaround:** Not needed.

### 7. CORS Restrictions

**Limitation:** Cross-origin requests are blocked from `file://` URLs.

**Impact:** ❌ None - All assets are embedded in the single HTML file.

**Workaround:** Not needed.

## Browser-Specific Issues

### Chrome

**Issue:** None known

**Status:** ✅ Works perfectly

**Notes:** Chrome has the best support for `file://` protocol with modern JavaScript.

### Firefox

**Issue:** None known

**Status:** ✅ Works perfectly

**Notes:** Firefox handles `file://` URLs well and supports all features.

### Safari

**Issue:** Stricter security policies

**Status:** ✅ Works with minor considerations

**Notes:** 
- May show security warnings for large files
- Generally works well on macOS
- iOS Safari may have additional restrictions

**Workaround:** Use desktop Safari or Chrome if issues occur.

### Edge

**Issue:** None known

**Status:** ✅ Works perfectly

**Notes:** Edge (Chromium) has same support as Chrome.

### Internet Explorer

**Issue:** Not supported

**Status:** ❌ Not supported

**Notes:** IE doesn't support modern JavaScript (ES6+) required by the Cloudscape UI.

**Workaround:** Use a modern browser (Chrome, Firefox, Edge, Safari).

## Security Considerations

### Why Browsers Restrict File:// URLs

Browsers restrict `file://` URLs to prevent:
- Malicious scripts from accessing local files
- Cross-site scripting (XSS) attacks
- Unauthorized file system access
- Privacy violations

### How Cloudscape UI Handles This

The Cloudscape UI is designed with these restrictions in mind:

1. **No External Requests** - All data embedded in HTML
2. **No File System Access** - Only reads embedded data
3. **No Local Storage** - Doesn't persist any data
4. **No Cookies** - Doesn't track users
5. **Self-Contained** - Single file with all assets

### Is It Safe?

✅ **Yes!** The Cloudscape UI:
- Doesn't access your file system
- Doesn't make network requests
- Doesn't store any data
- Doesn't track you
- Is completely self-contained

## Alternative: Using a Local Web Server

If you encounter issues with `file://` protocol, you can serve the report via a local web server.

### Option 1: Python HTTP Server

```bash
cd adminlte/aws/{ACCOUNT_ID}
python3 -m http.server 8000

# Open in browser:
# http://localhost:8000/index.html
```

### Option 2: Node.js HTTP Server

```bash
cd adminlte/aws/{ACCOUNT_ID}
npx http-server -p 8000

# Open in browser:
# http://localhost:8000/index.html
```

### Option 3: PHP Built-in Server

```bash
cd adminlte/aws/{ACCOUNT_ID}
php -S localhost:8000

# Open in browser:
# http://localhost:8000/index.html
```

### When to Use a Web Server

Use a local web server if:
- You encounter browser-specific issues
- You need to test with `http://` protocol
- You're developing/debugging the UI
- Your organization requires it

**Note:** For normal use, `file://` protocol works perfectly fine.

## Troubleshooting

### Issue: Page is blank when opened

**Possible Causes:**
1. JavaScript is disabled
2. File is corrupted
3. Browser doesn't support ES6+

**Solutions:**
1. Enable JavaScript in browser settings
2. Re-generate the report
3. Try a different browser (Chrome recommended)
4. Check browser console (F12) for errors

### Issue: URLs don't work

**Possible Cause:** Expecting traditional routing

**Solution:** Use hash-based URLs:
- ✅ `file:///path/index.html#/service/s3`
- ❌ `file:///path/index.html/service/s3`

### Issue: Browser shows security warning

**Possible Cause:** Large file size or browser security settings

**Solutions:**
1. Click "Allow" or "Continue" if prompted
2. Add file to browser's trusted locations
3. Use a different browser
4. Use local web server (see above)

### Issue: Charts not rendering

**Possible Causes:**
1. Browser doesn't support modern JavaScript
2. JavaScript error occurred

**Solutions:**
1. Use modern browser (Chrome, Firefox, Edge, Safari 14+)
2. Check browser console (F12) for errors
3. Try a different browser

### Issue: Data not loading

**Possible Causes:**
1. File is corrupted
2. Data wasn't embedded properly
3. JavaScript error

**Solutions:**
1. Check file size (should be ~2MB)
2. Re-generate report
3. Check browser console: `window.__REPORT_DATA__`
4. Try a different browser

## Best Practices

### For Users

1. **Use Modern Browsers** - Chrome, Firefox, Edge, or Safari 14+
2. **Enable JavaScript** - Required for the UI to work
3. **Don't Modify Files** - Open the HTML file as-is
4. **Check File Size** - Should be ~2MB (if much smaller, may be corrupted)
5. **Use File:// Protocol** - No web server needed for normal use

### For Developers

1. **Test with File://** - Always test with `file://` protocol
2. **No External Dependencies** - Keep everything self-contained
3. **Use Hash Routing** - Required for `file://` compatibility
4. **Embed All Assets** - CSS, JS, images all inlined
5. **No Network Requests** - Design for offline use

### For Organizations

1. **Distribute Single File** - Easy to share via email/file share
2. **No Server Required** - Users can open directly
3. **Works Offline** - No internet connection needed
4. **Secure** - No external dependencies or tracking
5. **Cross-Platform** - Works on Windows, macOS, Linux

## Comparison: File:// vs HTTP://

| Feature | File:// | HTTP:// |
|---------|---------|---------|
| **Setup** | None | Web server required |
| **Offline** | ✅ Yes | ⚠️ Depends on server |
| **Security** | ✅ Local only | ⚠️ Network accessible |
| **Distribution** | ✅ Easy (single file) | ⚠️ Requires hosting |
| **AJAX** | ❌ Blocked | ✅ Allowed |
| **Routing** | ⚠️ Hash-based only | ✅ Any routing |
| **Local Storage** | ⚠️ Restricted | ✅ Full access |
| **Performance** | ✅ Fast (local) | ⚠️ Depends on network |

**Recommendation:** Use `file://` for normal use. Only use `http://` if you encounter specific issues or have organizational requirements.

## Technical Details

### How Data Embedding Works

The Python `OutputGenerator` embeds data during build:

```python
# Read JSON data
with open('api-full.json', 'r') as f:
    json_data = f.read()

# Embed in HTML
data_script = f'''<script>
window.__REPORT_DATA__ = {json_data};
</script>'''

# Insert before </head>
html_content = html_content.replace('</head>', f'{data_script}\n</head>')
```

### Why Single File?

**Benefits:**
- Easy to distribute (one file)
- Works with `file://` protocol
- No broken asset links
- Fully self-contained
- Offline-capable

**Trade-offs:**
- Larger file size (~2MB vs ~23KB + assets)
- Longer initial load (but still < 2s)
- Can't cache assets separately

**Verdict:** Benefits outweigh trade-offs for this use case.

## Future Considerations

### Potential Improvements

1. **Progressive Loading** - Load data in chunks for large reports
2. **Compression** - Further reduce file size
3. **Caching** - Cache parsed data in memory
4. **Lazy Loading** - Load components on demand

### Limitations We Accept

1. **File Size** - 2MB is acceptable for offline use
2. **Hash Routing** - Required for `file://` compatibility
3. **No Server Features** - Not needed for this use case
4. **Single File** - Simplicity over optimization

## Summary

The Cloudscape UI is designed to work perfectly with the `file://` protocol:

✅ **Works out of the box** - No configuration needed
✅ **No web server required** - Open directly in browser
✅ **Fully offline** - No network requests
✅ **Secure** - No external dependencies
✅ **Cross-platform** - Works on all major browsers
✅ **Easy to distribute** - Single HTML file

The browser security restrictions that exist for `file://` URLs don't affect the Cloudscape UI because it's designed to be completely self-contained.

**Bottom line:** Just open the HTML file in your browser and it works!

## Getting Help

If you encounter issues with the `file://` protocol:

1. Check this document for known issues
2. Try a different browser (Chrome recommended)
3. Check browser console (F12) for errors
4. Try using a local web server (see above)
5. Report the issue with browser details

Most issues can be resolved by using a modern browser with JavaScript enabled.
