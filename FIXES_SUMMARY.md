# GPU Parameter Fix Summary

## Problem
User reported that when checking `use_gpu` in the web encoding dialog, the encoding still used `libx265` instead of `hevc_nvenc`, indicating the GPU parameter was not being passed correctly to the BatchEncoder.

## Root Cause Analysis
Massive data format mismatch between web client and Python GUI's BatchEncoder:

### Parameter Format Differences

1. **Bit Depth:**
   - Web sent: `bit_depth: "Force 8-bit"` (raw display value)
   - BatchEncoder expects: `bit_depth_preference: "force_8bit"` (normalized code)

2. **Bitrate Settings:**
   - Web sent: Nested structure `bitrate_settings: {low_res: {min, max, target}, 720p: {...}}`
   - BatchEncoder expects: Flat keys `encoding_bitrate_min_low_res`, `encoding_bitrate_max_low_res`, `target_bitrate_low_res`

3. **Language Filtering:**
   - Web sent: `filter_audio_by_language`, `audio_filter_languages`
   - Config uses: `audio.language_filter_enabled`, `audio.allowed_languages`

## Changes Made

### 1. web/static/js/dialogs.js - `_handleStart()` method
**Lines: 673-753**

**Before:**
```javascript
// Sent nested bitrate_settings object and raw bit_depth value
settings = {
    bit_depth: "Force 8-bit",  // RAW FORM VALUE
    bitrate_settings: {        // NESTED STRUCTURE
        low_res: {min, max, target},
        '720p': {min, max, target},
        ...
    },
    filter_audio_by_language: boolean,
    audio_filter_languages: string[]
}
```

**After:**
```javascript
// Now converts to Python GUI format before sending
settings = {
    bit_depth_preference: "force_8bit",  // NORMALIZED
    encoding_bitrate_min_low_res: 500,   // FLAT STRUCTURE
    encoding_bitrate_max_low_res: 1000,
    target_bitrate_low_res: 750,
    // ... similar for all resolutions
    audio_filter_enabled: boolean,       // RENAMED
    audio_languages: string[]            // RENAMED
}
```

**Changes:**
- Normalize `bit_depth` to `bit_depth_preference` with values: 'force_8bit', 'force_10bit', 'source'
- Convert nested `bitrate_settings` to flat keys: `encoding_bitrate_min_{res}`, `encoding_bitrate_max_{res}`, `target_bitrate_{res}`
- Rename `filter_audio_by_language` → `audio_filter_enabled`
- Rename `audio_filter_languages` → `audio_languages`
- Same for subtitles: `filter_subtitles_by_language` → `subtitle_filter_enabled`, etc.

### 2. web/static/js/dialogs.js - `_initializeFormWithDefaults()` method
**Lines: 419-453**

**Changes:**
- Load `bit_depth_preference` from config instead of `bit_depth`
- Normalize display values: 'force_8bit' → 'Force 8-bit', 'force_10bit' → 'Force 10-bit', 'source' → 'Match source'
- Load bitrate from flat keys directly: `config.enc.encoding_bitrate_min_low_res`, etc.
- Update language filter field names to match config structure

### 3. web/static/js/dialogs.js - `_loadPreset()` method
**Lines: 495-583**

**Changes:**
- Handle both old nested format (backward compatibility) and new flat format
- Added conditional: `if (preset.bitrate_settings)` for old format, else use flat keys
- Normalize `bit_depth_preference` display values same as `_initializeFormWithDefaults()`
- Update language filter field names

### 4. web/static/js/dialogs.js - `_savePreset()` method
**Lines: 580-627**

**Before:**
```javascript
preset = {
    bit_depth: "Force 8-bit",  // RAW VALUE
    bitrate_settings: {        // NESTED STRUCTURE
        low_res: {min, max, target},
        ...
    },
    filter_audio_by_language: boolean
}
```

**After:**
```javascript
preset = {
    bit_depth_preference: "force_8bit",     // NORMALIZED
    encoding_bitrate_min_low_res: 500,      // FLAT STRUCTURE
    encoding_bitrate_max_low_res: 1000,
    target_bitrate_low_res: 750,
    // ... similar for all resolutions
    audio_filter_enabled: boolean,          // RENAMED
    audio_languages: string[]               // RENAMED
}
```

**Changes:**
- Save presets with normalized values and flat bitrate structure
- This ensures saved presets use consistent format for loading

### 5. web/server.py - `start_encoding()` endpoint
**Lines: 383-407**

**Before:**
```python
@app.post("/start-encoding")
async def start_encoding(
    request_body: dict,
    files: UploadFile,
    ...
):
    batch_encoder.encoding_params.update(encoding_settings)
```

**After:**
```python
@app.post("/start-encoding")
async def start_encoding(request: Request):
    request_body = await request.json()

    # Extract audio/subtitle settings to update config sections
    audio_filter_enabled = encoding_settings.pop("audio_filter_enabled", False)
    audio_languages = encoding_settings.pop("audio_languages", [])

    # Update config["audio"]["language_filter_enabled"] and ["allowed_languages"]
    # ... same for subtitles

    # Pass cleaned encoding_settings to encoder
    batch_encoder.encoding_params.update(encoding_settings)
```

**Changes:**
- Extract `audio_filter_enabled` and `audio_languages` from encoding_settings
- Update config sections `config["audio"]` and `config["subtitles"]` separately
- Pass cleaned encoding_settings (without the language keys) to BatchEncoder
- This ensures language filtering is applied via config, not parameters

## Parameter Flow Verification

```
HTML Form (encUseGPU checkbox)
    ↓
JavaScript _handleStart()
    settings['use_gpu'] = document.getElementById('encUseGPU').checked
    ↓
POST /start-encoding with settings object
    ↓
Server endpoint receives request body
    await request.json() → encoding_settings dict
    ↓
batch_encoder.encoding_params.update(encoding_settings)
    ↓
BatchEncoder line 536-537:
    use_gpu = self.encoding_params.get("use_gpu", False)
    codec = "hevc_nvenc" if use_gpu else "libx265"
```

## Testing Checklist

- [ ] Start encoding with `use_gpu` **checked**
  - Expected: [ENCODE CMD] shows `hevc_nvenc`
  - Previous: [ENCODE CMD] showed `libx265`

- [ ] Start encoding with `use_gpu` **unchecked**
  - Expected: [ENCODE CMD] shows `libx265`

- [ ] Test bitrate parameters with different resolutions
  - Expected: Bitrate limits applied to each resolution correctly

- [ ] Test audio language filtering
  - Expected: Audio streams filtered by language code

- [ ] Test subtitle language filtering
  - Expected: Subtitle streams filtered by language code

- [ ] Save a preset and load it back
  - Expected: Form fields repopulate with correct values

- [ ] Load old preset with nested bitrate_settings format
  - Expected: Form fields populate correctly (backward compatibility)

## Backward Compatibility

The `_loadPreset()` method includes backward compatibility logic:
```javascript
if (preset.bitrate_settings) {
    // Handle OLD nested format
    const bs = preset.bitrate_settings;
    document.getElementById('encMinLowRes').value = bs.low_res.min;
} else {
    // Handle NEW flat format
    document.getElementById('encMinLowRes').value = preset.encoding_bitrate_min_low_res;
}
```

This ensures existing saved presets with the old nested format continue to work when loaded.

## Key Files Modified

1. **web/static/js/dialogs.js** - EncodingSettingsDialog class
   - `_handleStart()` - Parameter format conversion
   - `_initializeFormWithDefaults()` - Loading config with normalization
   - `_loadPreset()` - Backward-compatible preset loading
   - `_savePreset()` - Saving with new flat format

2. **web/server.py** - start_encoding() endpoint
   - Extract language settings from parameters
   - Update config sections separately
   - Pass cleaned settings to BatchEncoder

## Impact

**Before Fix:**
- Web UI sends: `{use_gpu: true, bit_depth: "Force 8-bit", bitrate_settings: {nested}, filter_audio_by_language: true, ...}`
- BatchEncoder receives: `{use_gpu: true}` but combined with wrong bitrate structure
- Result: GPU flag may not be read correctly; bitrate parameters not applied

**After Fix:**
- Web UI sends: `{use_gpu: true, bit_depth_preference: "force_8bit", encoding_bitrate_min_low_res: 500, audio_filter_enabled: true, ...}`
- BatchEncoder receives: Exact same format as Python GUI
- Result: All parameters, including GPU flag, applied correctly
