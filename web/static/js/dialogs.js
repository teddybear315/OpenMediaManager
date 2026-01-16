/**
 * Dialog utilities for Open Media Manager web interface
 */

const Dialogs = {
    // Alert dialog
    async alert(title, message) {
        console.log('Dialogs.alert called:', title, message);
        return new Promise((resolve) => {
            const dialog = document.getElementById('alertDialog');
            const dialogTitle = document.getElementById('alertTitle');
            const dialogMessage = document.getElementById('alertMessage');
            const okBtn = document.getElementById('alertOkBtn');

            if (!dialog) {
                console.error('alertDialog element not found');
                resolve();
                return;
            }

            dialogTitle.textContent = title;
            dialogMessage.textContent = message;
            dialog.classList.add('active');
            console.log('Alert dialog shown');

            const closeDialog = () => {
                dialog.classList.remove('active');
                okBtn.removeEventListener('click', closeDialog);
                resolve();
            };

            okBtn.addEventListener('click', closeDialog);
        });
    },

    // Confirm dialog
    async confirm(title, message) {
        console.log('Dialogs.confirm called:', title, message);
        return new Promise((resolve) => {
            const dialog = document.getElementById('confirmDialog');
            const dialogTitle = document.getElementById('confirmTitle');
            const dialogMessage = document.getElementById('confirmMessage');
            const confirmBtn = document.getElementById('confirmOkBtn');
            const cancelBtn = document.getElementById('confirmCancelBtn');

            if (!dialog) {
                console.error('confirmDialog element not found');
                resolve(false);
                return;
            }

            dialogTitle.textContent = title;
            dialogMessage.textContent = message;
            dialog.classList.add('active');
            console.log('Confirm dialog shown');

            const closeDialog = (result) => {
                dialog.classList.remove('active');
                confirmBtn.removeEventListener('click', onConfirm);
                cancelBtn.removeEventListener('click', onCancel);
                resolve(result);
            };

            const onConfirm = () => closeDialog(true);
            const onCancel = () => closeDialog(false);

            confirmBtn.addEventListener('click', onConfirm);
            cancelBtn.addEventListener('click', onCancel);
        });
    }
};

// Settings Dialog
class SettingsDialog {
    constructor() {
        this.dialog = document.getElementById('settingsDialog');
        this.form = document.getElementById('settingsForm');
        this.closeBtn = this.dialog.querySelector('.modal-close');
        this.cancelBtn = document.getElementById('cancelSettingsBtn');
        this.saveBtn = document.getElementById('saveSettingsBtn');

        this.attachEventListeners();
        this._setupTabHandlers();
    }

    attachEventListeners() {
        this.closeBtn.addEventListener('click', () => this.close());
        this.cancelBtn.addEventListener('click', () => this.close());
        this.saveBtn.addEventListener('click', () => this.save());
    }

    open() {
        this.dialog.classList.add('active');
        this.loadSettings();
    }

    close() {
        this.dialog.classList.remove('active');
    }

    async loadSettings() {
        try {
            const config = await Utils.API.getConfig();
            this.populateForm(config);
        } catch (error) {
            console.error('Failed to load settings:', error);
            await Dialogs.alert('Error', 'Failed to load settings');
        }
    }

    populateForm(config) {
        // General tab
        document.getElementById('mediaPath').value = config.media_path || '';
        document.getElementById('scanThreads').value = config.scan_threads || 8;
        document.getElementById('audioLangs').value = (config.preferred_audio_languages || ['eng']).join(', ');
        document.getElementById('subtitleLangs').value = (config.preferred_subtitle_languages || ['eng']).join(', ');

        // Quality standards
        const qs = config.quality_standards || {};
        document.getElementById('minLowRes').value = qs.min_bitrate_low_res || 500;
        document.getElementById('maxLowRes').value = qs.max_bitrate_low_res || 1000;
        document.getElementById('min720p').value = qs.min_bitrate_720p || 1000;
        document.getElementById('max720p').value = qs.max_bitrate_720p || 2000;
        document.getElementById('min1080p').value = qs.min_bitrate_1080p || 2000;
        document.getElementById('max1080p').value = qs.max_bitrate_1080p || 4000;
        document.getElementById('min1440p').value = qs.min_bitrate_1440p || 4000;
        document.getElementById('max1440p').value = qs.max_bitrate_1440p || 6000;
        document.getElementById('min4k').value = qs.min_bitrate_4k || 6000;
        document.getElementById('max4k').value = qs.max_bitrate_4k || 10000;
        document.getElementById('subtitleCheck').value = qs.subtitle_check || 'ignore';
        document.getElementById('coverArtCheck').value = qs.cover_art_check || 'ignore';
    }

    async save() {
        try {
            const config = {
                media_path: document.getElementById('mediaPath').value,
                scan_threads: parseInt(document.getElementById('scanThreads').value),
                preferred_audio_languages: document.getElementById('audioLangs').value.split(',').map(l => l.trim()).filter(l => l),
                preferred_subtitle_languages: document.getElementById('subtitleLangs').value.split(',').map(l => l.trim()).filter(l => l),
                quality_standards: {
                    min_bitrate_low_res: parseInt(document.getElementById('minLowRes').value),
                    max_bitrate_low_res: parseInt(document.getElementById('maxLowRes').value),
                    min_bitrate_720p: parseInt(document.getElementById('min720p').value),
                    max_bitrate_720p: parseInt(document.getElementById('max720p').value),
                    min_bitrate_1080p: parseInt(document.getElementById('min1080p').value),
                    max_bitrate_1080p: parseInt(document.getElementById('max1080p').value),
                    min_bitrate_1440p: parseInt(document.getElementById('min1440p').value),
                    max_bitrate_1440p: parseInt(document.getElementById('max1440p').value),
                    min_bitrate_4k: parseInt(document.getElementById('min4k').value),
                    max_bitrate_4k: parseInt(document.getElementById('max4k').value),
                    subtitle_check: document.getElementById('subtitleCheck').value,
                    cover_art_check: document.getElementById('coverArtCheck').value
                }
            };

            const result = await Utils.API.updateConfig(config);
            if (result.status === 'success') {
                Utils.Logger.success('Settings saved successfully');
                Utils.State.set('config', config);
                this.close();
            }
        } catch (error) {
            console.error('Failed to save settings:', error);
            await Dialogs.alert('Error', 'Failed to save settings');
        }
    }

    _setupTabHandlers() {
        document.querySelectorAll('.settings-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;

                // Hide all tabs
                document.querySelectorAll('.settings-tab-content').forEach(content => {
                    content.style.display = 'none';
                });
                document.querySelectorAll('.settings-tab').forEach(t => {
                    t.classList.remove('active');
                    t.style.borderBottom = '2px solid transparent';
                });

                // Show selected tab
                document.getElementById(`${tabName}-tab`).style.display = 'block';
                tab.classList.add('active');
                tab.style.borderBottom = '2px solid var(--primary-color)';
            });
        });
    }
}

// Input Dialog (for future use with form inputs)
class InputDialog {
    constructor(title, fields) {
        this.title = title;
        this.fields = fields; // Array of {name, label, type, required, value}
        this.result = null;
    }

    async show() {
        return new Promise((resolve) => {
            const dialog = document.createElement('div');
            dialog.className = 'modal-overlay active';

            let formHTML = '<form>';
            this.fields.forEach(field => {
                formHTML += `
                    <div class="form-group">
                        <label for="${field.name}">${field.label}:</label>
                        <input type="${field.type || 'text'}"
                               id="${field.name}"
                               class="input-control"
                               value="${field.value || ''}"
                               ${field.required ? 'required' : ''}>
                    </div>
                `;
            });
            formHTML += '</form>';

            dialog.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>${this.title}</h2>
                        <button type="button" class="modal-close">&times;</button>
                    </div>
                    <div class="modal-body">
                        ${formHTML}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary cancel-btn">Cancel</button>
                        <button type="button" class="btn btn-primary ok-btn">OK</button>
                    </div>
                </div>
            `;

            document.body.appendChild(dialog);

            const closeDialog = (result) => {
                dialog.remove();
                resolve(result);
            };

            dialog.querySelector('.modal-close').addEventListener('click', () => closeDialog(null));
            dialog.querySelector('.cancel-btn').addEventListener('click', () => closeDialog(null));
            dialog.querySelector('.ok-btn').addEventListener('click', () => {
                const values = {};
                this.fields.forEach(field => {
                    values[field.name] = document.getElementById(field.name).value;
                });
                closeDialog(values);
            });

            // Focus first input
            const firstInput = dialog.querySelector('input');
            if (firstInput) firstInput.focus();
        });
    }
}

// Progress Dialog
class ProgressDialog {
    constructor(title, showProgress = true) {
        this.title = title;
        this.showProgress = showProgress;
        this.dialog = null;
        this.progressBar = null;
    }

    show() {
        this.dialog = document.createElement('div');
        this.dialog.className = 'modal-overlay active';

        let progressHTML = '';
        if (this.showProgress) {
            progressHTML = `
                <div class="form-group">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                    </div>
                    <div class="text-center text-muted" id="progressText">0%</div>
                </div>
            `;
        }

        this.dialog.innerHTML = `
            <div class="modal-content modal-small">
                <div class="modal-header">
                    <h2>${this.title}</h2>
                </div>
                <div class="modal-body">
                    ${progressHTML}
                    <p id="progressMessage"></p>
                </div>
            </div>
        `;

        document.body.appendChild(this.dialog);
        this.progressBar = this.dialog.querySelector('#progressFill');
    }

    setProgress(percent) {
        if (this.progressBar) {
            this.progressBar.style.width = `${percent}%`;
            const text = this.dialog.querySelector('#progressText');
            if (text) text.textContent = `${Math.round(percent)}%`;
        }
    }

    setMessage(message) {
        const msgEl = this.dialog.querySelector('#progressMessage');
        if (msgEl) msgEl.textContent = message;
    }

    close() {
        if (this.dialog) {
            this.dialog.remove();
            this.dialog = null;
        }
    }
}

// Encoding Settings Dialog
class EncodingSettingsDialog {
    constructor(batchResolutions = []) {
        this.dialog = document.getElementById('encodingSettingsDialog');
        this.batchResolutions = batchResolutions;
        this.presets = {};
        this.currentProfile = null;
        this._setupEventListeners();
        this._setupConditionalFields();
    }

    _setupEventListeners() {
        // Dialog controls
        const closeBtn = this.dialog.querySelector('.modal-close');
        const cancelBtn = document.getElementById('encCancelBtn');
        const startBtn = document.getElementById('encStartBtn');

        closeBtn?.addEventListener('click', () => this.close());
        cancelBtn?.addEventListener('click', () => this.close());
        startBtn?.addEventListener('click', () => this._handleStart());

        // Preset controls
        document.getElementById('encProfile')?.addEventListener('change', (e) => this._loadPreset(e.target.value));
        document.getElementById('encSaveProfile')?.addEventListener('click', () => this._savePreset());
        document.getElementById('encDeleteProfile')?.addEventListener('click', () => this._deletePreset());
    }

    _setupConditionalFields() {
        const cqField = document.getElementById('encCQ');
        const useTargetBitrate = document.getElementById('encUseTargetBitrate');
        const useGPU = document.getElementById('encUseGPU');
        const threadCountField = document.getElementById('encThreads');
        const useMinMaxBitrate = document.getElementById('encUseMinMaxBitrate');
        const filterAudio = document.getElementById('encFilterAudio');
        const filterSubs = document.getElementById('encFilterSubs');

        useTargetBitrate?.addEventListener('change', () => {
            const enabled = !useTargetBitrate.checked;
            cqField.disabled = !enabled;
            this._updateTargetBitrateVisibility();
        });

        useGPU?.addEventListener('change', () => {
            const enabled = !useGPU.checked;
            threadCountField.disabled = !enabled;
        });

        useMinMaxBitrate?.addEventListener('change', () => {
            this._updateBitrateFieldsState();
        });

        filterAudio?.addEventListener('change', () => {
            const group = document.getElementById('encAudioLangsGroup');
            if (group) group.classList.toggle('form-group-hidden', !filterAudio.checked);
        });

        filterSubs?.addEventListener('change', () => {
            const group = document.getElementById('encSubsLangsGroup');
            if (group) group.classList.toggle('form-group-hidden', !filterSubs.checked);
        });
    }

    async show() {
        // Load config to get encoding defaults
        let encodingDefaults = {};
        try {
            const config = await Utils.API.getConfig();
            encodingDefaults = config.encoding || {};
        } catch (error) {
            console.error('Failed to load config defaults:', error);
        }

        // Initialize form with defaults from config
        this._initializeFormWithDefaults(encodingDefaults);

        // Load presets from server using the dedicated encoding profiles API
        try {
            const response = await Utils.API.getEncodingProfiles();
            this.presets = response.profiles || {};
            console.log('[EncodingSettingsDialog] Loaded presets:', Object.keys(this.presets));
            this._populatePresetDropdown();
        } catch (error) {
            console.error('Failed to load encoding presets:', error);
        }

        // Update resolution visibility based on batch
        this._updateResolutionVisibility();

        // Show dialog
        this.dialog.classList.add('active');

        return new Promise((resolve) => {
            this._resolveDialog = resolve;
        });
    }

    _initializeFormWithDefaults(enc) {
        /**Initialize all form fields with defaults from config encoding settings*/
        document.getElementById('encCodec').value = enc.codec_type || 'x265';
        document.getElementById('encPreset').value = enc.preset || 'veryfast';
        document.getElementById('encCQ').value = enc.cq || 22;
        // Set level, converting 'auto' to empty string for "Auto (ignore)" option
        const levelField = document.getElementById('encLevel');
        const levelValue = enc.level || '';
        levelField.value = (levelValue.toLowerCase && levelValue.toLowerCase() === 'auto') ? '' : levelValue;

        // Set bit_depth_preference to option value (defaults to 'source')
        const bitDepthPref = enc.bit_depth_preference || 'source';
        document.getElementById('encBitDepth').value = bitDepthPref;

        document.getElementById('encUseGPU').checked = enc.use_gpu || false;
        document.getElementById('encThreads').value = enc.thread_count || 4;
        document.getElementById('encTuneAnimation').checked = enc.tune_animation || false;
        document.getElementById('encSkipVideo').checked = enc.skip_video_encoding || false;
        document.getElementById('encSkipAudio').checked = enc.skip_audio_encoding || false;
        document.getElementById('encSkipSubs').checked = enc.skip_subtitle_encoding || false;
        document.getElementById('encSkipCoverArt').checked = enc.skip_cover_art !== false;
        document.getElementById('encUseMinMaxBitrate').checked = enc.use_bitrate_limits || false;
        document.getElementById('encUseTargetBitrate').checked = enc.use_target_bitrate || false;

        // Update conditional field states based on initial values
        this._updateBitrateFieldsState();
        this._updateTargetBitrateVisibility();
        this._updateGPUFieldState();

        // Initialize bitrate settings
        document.getElementById('encMinLowRes').value = enc.encoding_bitrate_min_low_res || 500;
        document.getElementById('encMaxLowRes').value = enc.encoding_bitrate_max_low_res || 1000;
        document.getElementById('encTargetLowRes').value = enc.target_bitrate_low_res || 800;
        document.getElementById('encMin720p').value = enc.encoding_bitrate_min_720p || 1000;
        document.getElementById('encMax720p').value = enc.encoding_bitrate_max_720p || 2000;
        document.getElementById('encTarget720p').value = enc.target_bitrate_720p || 1500;
        document.getElementById('encMin1080p').value = enc.encoding_bitrate_min_1080p || 2000;
        document.getElementById('encMax1080p').value = enc.encoding_bitrate_max_1080p || 4000;
        document.getElementById('encTarget1080p').value = enc.target_bitrate_1080p || 3000;
        document.getElementById('encMin1440p').value = enc.encoding_bitrate_min_1440p || 4000;
        document.getElementById('encMax1440p').value = enc.encoding_bitrate_max_1440p || 6000;
        document.getElementById('encTarget1440p').value = enc.target_bitrate_1440p || 5000;
        document.getElementById('encMin4k').value = enc.encoding_bitrate_min_4k || 6000;
        document.getElementById('encMax4k').value = enc.encoding_bitrate_max_4k || 10000;
        document.getElementById('encTarget4k').value = enc.target_bitrate_4k || 8000;

        // Initialize language filters
        document.getElementById('encFilterAudio').checked = false;
        document.getElementById('encAudioLangs').value = 'eng';
        document.getElementById('encFilterSubs').checked = false;
        document.getElementById('encSubLangs').value = 'eng';
    }

    close() {
        this.dialog.classList.remove('active');
        if (this._resolveDialog) {
            this._resolveDialog(null);
            this._resolveDialog = null;
        }
    }

    _populatePresetDropdown() {
        const select = document.getElementById('encProfile');
        const existingOptions = select.querySelectorAll('option:not([value=""])');
        existingOptions.forEach(opt => opt.remove());

        const presetNames = Object.keys(this.presets);
        console.log('[EncodingSettingsDialog] _populatePresetDropdown - adding', presetNames.length, 'presets:', presetNames);

        presetNames.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            select.appendChild(option);
        });
    }

    _loadPreset(name) {
        if (!name || !this.presets[name]) return;

        const preset = this.presets[name];
        document.getElementById('encCodec').value = preset.codec_type || 'x265';
        document.getElementById('encPreset').value = preset.preset || 'veryfast';
        document.getElementById('encCQ').value = preset.cq || 22;
        // Set level, converting 'auto' to empty string for "Auto (ignore)" option
        const levelField = document.getElementById('encLevel');
        const levelValue = preset.level || '';
        levelField.value = (levelValue.toLowerCase && levelValue.toLowerCase() === 'auto') ? '' : levelValue;

        // Set bit_depth_preference to option value (defaults to 'source')
        const bitDepthPref = preset.bit_depth_preference || 'source';
        document.getElementById('encBitDepth').value = bitDepthPref;

        document.getElementById('encUseGPU').checked = preset.use_gpu || false;
        document.getElementById('encThreads').value = preset.thread_count || 4;
        document.getElementById('encTuneAnimation').checked = preset.tune_animation || false;
        document.getElementById('encSkipVideo').checked = preset.skip_video_encoding || false;
        document.getElementById('encSkipAudio').checked = preset.skip_audio_encoding || false;
        document.getElementById('encSkipSubs').checked = preset.skip_subtitle_encoding || false;
        document.getElementById('encSkipCoverArt').checked = preset.skip_cover_art !== false;
        document.getElementById('encUseMinMaxBitrate').checked = preset.use_bitrate_limits || false;
        document.getElementById('encUseTargetBitrate').checked = preset.use_target_bitrate || false;

        // Load bitrate settings - handle both old nested format and new flat format
        if (preset.bitrate_settings) {
            // Old nested format
            const bs = preset.bitrate_settings;
            if (bs.low_res) {
                document.getElementById('encMinLowRes').value = bs.low_res.min || 500;
                document.getElementById('encMaxLowRes').value = bs.low_res.max || 1000;
                document.getElementById('encTargetLowRes').value = bs.low_res.target || 800;
            }
            if (bs['720p']) {
                document.getElementById('encMin720p').value = bs['720p'].min || 1000;
                document.getElementById('encMax720p').value = bs['720p'].max || 2000;
                document.getElementById('encTarget720p').value = bs['720p'].target || 1500;
            }
            if (bs['1080p']) {
                document.getElementById('encMin1080p').value = bs['1080p'].min || 2000;
                document.getElementById('encMax1080p').value = bs['1080p'].max || 4000;
                document.getElementById('encTarget1080p').value = bs['1080p'].target || 3000;
            }
            if (bs['1440p']) {
                document.getElementById('encMin1440p').value = bs['1440p'].min || 4000;
                document.getElementById('encMax1440p').value = bs['1440p'].max || 6000;
                document.getElementById('encTarget1440p').value = bs['1440p'].target || 5000;
            }
            if (bs['4k']) {
                document.getElementById('encMin4k').value = bs['4k'].min || 6000;
                document.getElementById('encMax4k').value = bs['4k'].max || 10000;
                document.getElementById('encTarget4k').value = bs['4k'].target || 8000;
            }
        } else {
            // New flat format
            document.getElementById('encMinLowRes').value = preset.encoding_bitrate_min_low_res || 500;
            document.getElementById('encMaxLowRes').value = preset.encoding_bitrate_max_low_res || 1000;
            document.getElementById('encTargetLowRes').value = preset.target_bitrate_low_res || 800;
            document.getElementById('encMin720p').value = preset.encoding_bitrate_min_720p || 1000;
            document.getElementById('encMax720p').value = preset.encoding_bitrate_max_720p || 2000;
            document.getElementById('encTarget720p').value = preset.target_bitrate_720p || 1500;
            document.getElementById('encMin1080p').value = preset.encoding_bitrate_min_1080p || 2000;
            document.getElementById('encMax1080p').value = preset.encoding_bitrate_max_1080p || 4000;
            document.getElementById('encTarget1080p').value = preset.target_bitrate_1080p || 3000;
            document.getElementById('encMin1440p').value = preset.encoding_bitrate_min_1440p || 4000;
            document.getElementById('encMax1440p').value = preset.encoding_bitrate_max_1440p || 6000;
            document.getElementById('encTarget1440p').value = preset.target_bitrate_1440p || 5000;
            document.getElementById('encMin4k').value = preset.encoding_bitrate_min_4k || 6000;
            document.getElementById('encMax4k').value = preset.encoding_bitrate_max_4k || 10000;
            document.getElementById('encTarget4k').value = preset.target_bitrate_4k || 8000;
        }

        // Load language filters
        document.getElementById('encFilterAudio').checked = preset.audio_filter_enabled || false;
        document.getElementById('encAudioLangs').value = (preset.audio_languages || ['eng']).join(', ');
        document.getElementById('encFilterSubs').checked = preset.subtitle_filter_enabled || false;
        document.getElementById('encSubLangs').value = (preset.subtitle_languages || ['eng']).join(', ');

        // Update field availability based on profile settings
        this._updateBitrateFieldsState();
        this._updateTargetBitrateVisibility();
        this._updateGPUFieldState();
        this._updateCQFieldState();
        this._updateLanguageFilterVisibility();

        this.currentProfile = name;
    }

    async _savePreset() {
        const profileName = prompt('Enter preset name:');
        if (!profileName) return;

        const preset = {
            codec_type: document.getElementById('encCodec').value,
            preset: document.getElementById('encPreset').value,
            cq: parseInt(document.getElementById('encCQ').value),
            level: document.getElementById('encLevel').value,
            use_gpu: document.getElementById('encUseGPU').checked,
            thread_count: parseInt(document.getElementById('encThreads').value),
            tune_animation: document.getElementById('encTuneAnimation').checked,
            skip_video_encoding: document.getElementById('encSkipVideo').checked,
            skip_audio_encoding: document.getElementById('encSkipAudio').checked,
            skip_subtitle_encoding: document.getElementById('encSkipSubs').checked,
            skip_cover_art: document.getElementById('encSkipCoverArt').checked,
            use_bitrate_limits: document.getElementById('encUseMinMaxBitrate').checked,
            use_target_bitrate: document.getElementById('encUseTargetBitrate').checked
        };

        // Normalize bit_depth_preference
        const bitDepthValue = document.getElementById('encBitDepth').value;
        if (bitDepthValue === 'Force 8-bit') {
            preset['bit_depth_preference'] = 'force_8bit';
        } else if (bitDepthValue === 'Force 10-bit') {
            preset['bit_depth_preference'] = 'force_10bit';
        } else {
            preset['bit_depth_preference'] = 'source';
        }

        // Save flat bitrate structure for all resolutions
        const bitrates = [
            { id: 'low_res', label: 'LowRes' },
            { id: '720p', label: '720p' },
            { id: '1080p', label: '1080p' },
            { id: '1440p', label: '1440p' },
            { id: '4k', label: '4k' }
        ];

        bitrates.forEach(({ id, label }) => {
            preset[`encoding_bitrate_min_${id}`] = parseInt(document.getElementById(`encMin${label}`).value);
            preset[`encoding_bitrate_max_${id}`] = parseInt(document.getElementById(`encMax${label}`).value);
            preset[`target_bitrate_${id}`] = parseInt(document.getElementById(`encTarget${label}`).value);
        });

        // Save language filter settings with normalized names
        preset['audio_filter_enabled'] = document.getElementById('encFilterAudio').checked;
        preset['audio_languages'] = document.getElementById('encAudioLangs').value.split(',').map(l => l.trim()).filter(l => l);
        preset['subtitle_filter_enabled'] = document.getElementById('encFilterSubs').checked;
        preset['subtitle_languages'] = document.getElementById('encSubLangs').value.split(',').map(l => l.trim()).filter(l => l);

        try {
            // Save to dedicated encoding profiles API
            await Utils.API.saveEncodingProfile(profileName, preset);

            // Reload presets from server
            const response = await Utils.API.getEncodingProfiles();
            this.presets = response.profiles || {};
            this._populatePresetDropdown();
            document.getElementById('encProfile').value = profileName;
            this.currentProfile = profileName;
            Utils.Logger.success(`Preset "${profileName}" saved`);
        } catch (error) {
            console.error('Failed to save preset:', error);
            await Dialogs.alert('Error', 'Failed to save preset');
        }
    }

    async _deletePreset() {
        const select = document.getElementById('encProfile');
        const name = select.value;
        if (!name) return;

        if (!confirm(`Delete preset "${name}"?`)) return;

        try {
            // Delete using dedicated encoding profiles API
            await Utils.API.deleteEncodingProfile(name);

            // Reload presets from server
            const response = await Utils.API.getEncodingProfiles();
            this.presets = response.profiles || {};
            this._populatePresetDropdown();
            document.getElementById('encProfile').value = '';
            this.currentProfile = null;
            Utils.Logger.success(`Preset "${name}" deleted`);
        } catch (error) {
            console.error('Failed to delete preset:', error);
            await Dialogs.alert('Error', 'Failed to delete preset');
        }
    }

    _handleStart() {
        const settings = {
            codec_type: document.getElementById('encCodec').value,
            preset: document.getElementById('encPreset').value,
            cq: parseInt(document.getElementById('encCQ').value),
            level: document.getElementById('encLevel').value || 'auto',  // Default to 'auto' if empty
            use_gpu: document.getElementById('encUseGPU').checked,
            thread_count: parseInt(document.getElementById('encThreads').value),
            tune_animation: document.getElementById('encTuneAnimation').checked,
            skip_video_encoding: document.getElementById('encSkipVideo').checked,
            skip_audio_encoding: document.getElementById('encSkipAudio').checked,
            skip_subtitle_encoding: document.getElementById('encSkipSubs').checked,
            skip_cover_art: document.getElementById('encSkipCoverArt').checked,
            use_bitrate_limits: document.getElementById('encUseMinMaxBitrate').checked,
            use_target_bitrate: document.getElementById('encUseTargetBitrate').checked
        };

        // Convert bit_depth to bit_depth_preference (normalize like Python GUI)
        const bitDepthValue = document.getElementById('encBitDepth').value;
        if (bitDepthValue === 'Force 8-bit') {
            settings['bit_depth_preference'] = 'force_8bit';
        } else if (bitDepthValue === 'Force 10-bit') {
            settings['bit_depth_preference'] = 'force_10bit';
        } else {
            settings['bit_depth_preference'] = 'source';
        }

        // Convert bitrate_settings to flat structure like Python GUI
        // encoding_bitrate_min_{res}, encoding_bitrate_max_{res}, target_bitrate_{res}
        const bitrateResolutions = [
            { id: 'low_res', label: 'LowRes' },
            { id: '720p', label: '720p' },
            { id: '1080p', label: '1080p' },
            { id: '1440p', label: '1440p' },
            { id: '4k', label: '4k' }
        ];

        bitrateResolutions.forEach(({ id, label }) => {
            const minElement = document.getElementById(`encMin${label}`);
            const maxElement = document.getElementById(`encMax${label}`);
            const targetElement = document.getElementById(`encTarget${label}`);

            // Always include bitrate settings, even if fields are disabled or hidden
            if (minElement) settings[`encoding_bitrate_min_${id}`] = parseInt(minElement.value) || 0;
            if (maxElement) settings[`encoding_bitrate_max_${id}`] = parseInt(maxElement.value) || 0;
            if (targetElement) settings[`target_bitrate_${id}`] = parseInt(targetElement.value) || 0;
        });

        // Handle language filtering settings
        // Audio filtering
        const audioFilterEnabled = document.getElementById('encFilterAudio');
        const audioLangsInput = document.getElementById('encAudioLangs');
        if (audioFilterEnabled && audioLangsInput) {
            settings['audio_filter_enabled'] = audioFilterEnabled.checked;
            settings['audio_languages'] = audioLangsInput.value.split(',').map(l => l.trim()).filter(l => l);
        }

        // Subtitle filtering
        const subFilterEnabled = document.getElementById('encFilterSubs');
        const subLangsInput = document.getElementById('encSubLangs');
        if (subFilterEnabled && subLangsInput) {
            settings['subtitle_filter_enabled'] = subFilterEnabled.checked;
            settings['subtitle_languages'] = subLangsInput.value.split(',').map(l => l.trim()).filter(l => l);
        }

        // Post-encode cleanup settings
        settings['auto_remove_broken'] = document.getElementById('encAutoRemoveBroken').checked;
        settings['auto_move_smaller'] = document.getElementById('encAutoMoveSmaller').checked;

        // Resolve with settings and close dialog
        if (this._resolveDialog) {
            this._resolveDialog(settings);
            this._resolveDialog = null;
        }
        this.dialog.classList.remove('active');
    }

    _updateResolutionVisibility() {
        const resolutionMap = {
            'low_res': ['lowResBitrateGroup'],
            '720p': ['res720pBitrateGroup'],
            '1080p': ['res1080pBitrateGroup'],
            '1440p': ['res1440pBitrateGroup'],
            '4k': ['res4kBitrateGroup']
        };

        Object.entries(resolutionMap).forEach(([res, groupIds]) => {
            const isInBatch = this.batchResolutions.includes(res);
            groupIds.forEach(groupId => {
                const group = document.getElementById(groupId);
                if (group) {
                    group.style.display = isInBatch ? 'block' : 'none';
                }
            });
        });
    }

    _updateTargetBitrateVisibility() {
        const useTarget = document.getElementById('encUseTargetBitrate').checked;
        const targetGroups = [
            'encTargetLowResGroup',
            'encTarget720pGroup',
            'encTarget1080pGroup',
            'encTarget1440pGroup',
            'encTarget4kGroup'
        ];

        targetGroups.forEach(groupId => {
            const group = document.getElementById(groupId);
            if (group) {
                group.style.display = useTarget ? 'block' : 'none';
            }
        });
    }

    _updateGPUFieldState() {
        const useGPU = document.getElementById('encUseGPU').checked;
        const threadCountField = document.getElementById('encThreads');
        if (threadCountField) {
            threadCountField.disabled = useGPU;
        }
    }

    _updateCQFieldState() {
        const useTargetBitrate = document.getElementById('encUseTargetBitrate').checked;
        const cqField = document.getElementById('encCQ');
        if (cqField) {
            cqField.disabled = useTargetBitrate;
        }
    }

    _updateLanguageFilterVisibility() {
        const filterAudio = document.getElementById('encFilterAudio').checked;
        const audioGroup = document.getElementById('encAudioLangsGroup');
        if (audioGroup) {
            audioGroup.classList.toggle('form-group-hidden', !filterAudio);
        }

        const filterSubs = document.getElementById('encFilterSubs').checked;
        const subsGroup = document.getElementById('encSubsLangsGroup');
        if (subsGroup) {
            subsGroup.classList.toggle('form-group-hidden', !filterSubs);
        }
    }

    _updateBitrateFieldsState() {
        const useMinMax = document.getElementById('encUseMinMaxBitrate').checked;
        const bitrateFields = document.querySelectorAll('[id^="encMin"], [id^="encMax"], [id^="encTarget"]');

        bitrateFields.forEach(field => {
            field.disabled = !useMinMax;
        });
    }
}

// Export for global use
window.Dialogs = Dialogs;
window.SettingsDialog = SettingsDialog;
window.InputDialog = InputDialog;
window.ProgressDialog = ProgressDialog;
window.EncodingSettingsDialog = EncodingSettingsDialog;
