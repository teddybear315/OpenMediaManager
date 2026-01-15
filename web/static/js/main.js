/**
 * Main application logic for Open Media Manager web interface
 */

class OpenMediaManager {
    constructor() {
        this.mediaFiles = [];
        this.selectedFiles = new Set();
        this.isEncoding = false;
        this.logWebSocket = null;
        this.settingsDialog = null;
        this.filteredFiles = [];
        this.groupedFiles = {};
        this.collapsedGroups = new Set();
        this.logVisible = false;
        this.encodingLogState = null;

        this.init();
    }

    async init() {
        console.log('Initializing Open Media Manager web interface...');

        // Set up UI elements
        this.setupUI();

        // Set up event listeners
        this.attachEventListeners();

        // Initialize dialogs
        this.settingsDialog = new SettingsDialog();

        // Connect WebSocket for logs
        await this.connectWebSocket();

        // Load initial data
        this.filteredFiles = await this.loadMedia();
        console.log(this.filteredFiles);

        console.log('Initialization complete');
    }

    setupUI() {
        // Initialize theme from localStorage or default to dark
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        const themeBtn = document.getElementById('themeBtn');
        themeBtn.textContent = savedTheme === 'dark' ? '☀️' : '🌙';

        // Set up responsive layout observer
        window.addEventListener('resize', () => this.onWindowResize());
        this.onWindowResize();
    }

    attachEventListeners() {
        // Header buttons
        document.getElementById('scanBtn').addEventListener('click', () => this.scanMedia());
        document.getElementById('themeBtn').addEventListener('click', () => this.toggleTheme());
        document.getElementById('settingsBtn').addEventListener('click', () => this.settingsDialog.open());

        // Media section
        document.getElementById('selectAllCheckbox').addEventListener('change', (e) => this.toggleSelectAll(e));
        document.getElementById('selectAllBtn').addEventListener('click', () => this.selectAll());
        document.getElementById('encodeBtn').addEventListener('click', () => this.startEncoding());
        document.getElementById('searchInput').addEventListener('input',
            Utils.debounce((e) => this.filterMedia(e.target.value), 300)
        );
        document.getElementById('filterStatus').addEventListener('change', (e) => this.filterByStatus(e.target.value));

        // Log section - toggle visibility
        const logSection = document.getElementById('logSection');
        const logHeader = logSection.querySelector('.section-header h2');
        logHeader.addEventListener('click', () => this.toggleLog());

        // Log buttons
        document.getElementById('clearLogBtn').addEventListener('click', () => this.clearLog());
        document.getElementById('stopEncodingBtn').addEventListener('click', () => this.stopEncoding());

        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.target.closest('.modal-overlay').classList.remove('active');
            });
        });

        // Close modals on background click
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('active');
                }
            });
        });
    }

    onWindowResize() {
        const layoutMode = Utils.Responsive.getLayoutMode();
        const main = document.querySelector('.app-main');

        if (layoutMode === 'horizontal') {
            // Desktop: horizontal split - let CSS handle flex ratios
            main.style.flexDirection = 'row';
        } else {
            // Mobile: vertical split
            main.style.flexDirection = 'column';
        }
    }

    async connectWebSocket() {
        this.logWebSocket = new Utils.LogWebSocket();

        try {
            await this.logWebSocket.connect();

            this.logWebSocket.onMessage((data) => {
                if (data.type === 'log') {
                    this.addLogEntry(data);
                } else if (data.type === 'encoding_start') {
                    this.isEncoding = true;
                    document.getElementById('encodeBtn').style.display = 'none';
                    document.getElementById('stopEncodingBtn').style.display = 'inline-block';
                    document.getElementById('stopEncodingBtn').disabled = false;
                    this.initializeEncodingLog(data.job_count);
                    Utils.Logger.info(`Joining encoding of ${data.job_count} files...`);
                    this.displayLog();
                } else if (data.type === 'encoding_complete') {
                    this.isEncoding = false;
                    document.getElementById('encodeBtn').style.display = 'inline-block';
                    document.getElementById('stopEncodingBtn').style.display = 'none';
                    const stopBtn = document.getElementById('stopEncodingBtn');
                    stopBtn.disabled = true;
                    stopBtn.textContent = 'Stop Encoding';
                    Utils.Logger.success('Encoding completed successfully');
                    this.finalizeEncodingLog();
                    this.displayLog();
                } else if (data.type === 'encoding_stopped') {
                    this.isEncoding = false;
                    document.getElementById('encodeBtn').style.display = 'inline-block';
                    document.getElementById('stopEncodingBtn').style.display = 'none';
                    const stopBtn = document.getElementById('stopEncodingBtn');
                    stopBtn.disabled = true;
                    stopBtn.textContent = 'Stop Encoding';
                    Utils.Logger.warning('Encoding stopped by user');
                    this.displayLog();
                } else if (data.type === 'file_start') {
                    this.handleFileStart(data);
                } else if (data.type === 'file_complete') {
                    this.handleFileComplete(data);
                } else if (data.type === 'file_progress') {
                    this.updateFileProgress(data);
                } else if (data.type === 'scan_complete') {
                    // Utils.Logger.success(`Media scan complete: ${data.count} files found`);
                    this.displayLog();
                }
            });
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            Utils.Logger.error('Failed to connect to server for live updates');
            this.displayLog();
        }
    }

    initializeEncodingLog(jobCount) {
        this.encodingLogState = {
            totalFiles: jobCount,
            currentFile: 0,
            totalOriginalSize: 0,
            totalEncodedSize: 0,
            fileStats: []
        };

        // Show progress containers
        document.getElementById('fileProgressContainer').style.display = 'block';
        if (jobCount > 1) {
            document.getElementById('batchProgressContainer').style.display = 'block';
        }
        document.getElementById('statisticsContainer').style.display = 'block';


    }

    finalizeEncodingLog() {
        if (!this.encodingLogState) return;

        const stats = this.encodingLogState;
        if (stats.fileStats.length === 0) return;

        const numFiles = stats.fileStats.length;
        const origSize = stats.totalOriginalSize / (1024 * 1024);
        const encSize = stats.totalEncodedSize / (1024 * 1024);
        const origUnit = origSize > 974 ? 'GB' : 'MB';
        const encUnit = encSize > 974 ? 'GB' : 'MB';
        const origValue = origSize > 974 ? origSize / 1024 : origSize;
        const encValue = encSize > 974 ? encSize / 1024 : encSize;

        const reduction = ((stats.totalOriginalSize - stats.totalEncodedSize) / stats.totalOriginalSize) * 100;
        const avgReduction = stats.fileStats.reduce((a, b) => a + b.reduction, 0) / numFiles;


        Utils.Logger.success(`✓ ENCODING COMPLETE`);
        Utils.Logger.info(`Files Processed: ${numFiles}`);
        Utils.Logger.info(`Total Original: ${origValue.toFixed(2)} ${origUnit} | Encoded: ${encValue.toFixed(2)} ${encUnit}`);
        Utils.Logger.success(`Overall Space Change: ${reduction > 0 ? '-' : '+'}${Math.abs(reduction).toFixed(2)}%`);
        Utils.Logger.info(`Average per File: ${avgReduction > 0 ? '-' : '+'}${Math.abs(avgReduction).toFixed(2)}%`);
    }

    handleFileStart(data) {
        this.encodingLogState.currentFile++;
        const num = this.encodingLogState.currentFile;


        Utils.Logger.info(`File ${num}/${this.encodingLogState.totalFiles}: ${data.filename}`);


        // Update file progress label
        const displayName = data.filename.length > 60 ? data.filename.substring(0, 57) + '...' : data.filename;
        document.getElementById('fileProgressLabel').textContent = `Encoding: ${displayName}`;
    }

    handleFileComplete(data) {
        const origSize = data.original_size / (1024 * 1024);
        const encSize = data.encoded_size / (1024 * 1024);
        const origUnit = origSize > 974 ? 'GB' : 'MB';
        const encUnit = encSize > 974 ? 'GB' : 'MB';
        const origValue = origSize > 974 ? origSize / 1024 : origSize;
        const encValue = encSize > 974 ? encSize / 1024 : encSize;

        const reduction = ((data.original_size - data.encoded_size) / data.original_size) * 100;

        if (data.success) {
            Utils.Logger.success(`✓ COMPLETE: ${data.filename}`);
            const color = reduction > 0 ? '#4caf50' : (reduction < 0 ? '#ff9800' : '#888888');
            const sign = reduction > 0 ? '-' : (reduction < 0 ? '+' : '');
            Utils.Logger.info(
                `File Size - Original: ${origValue.toFixed(2)} ${origUnit}, ` +
                `Encoded: ${encValue.toFixed(2)} ${encUnit}, ` +
                `Change: ${sign}${Math.abs(reduction).toFixed(2)}%`
            );

            // Update stats
            this.encodingLogState.totalOriginalSize += data.original_size;
            this.encodingLogState.totalEncodedSize += data.encoded_size;
            this.encodingLogState.fileStats.push({
                original: data.original_size,
                encoded: data.encoded_size,
                reduction: reduction
            });

            this.updateStatistics();
        } else {
            Utils.Logger.error(`✗ FAILED: ${data.filename}`);
        }
    }

    updateFileProgress(data) {
        const progress = data.progress || 0;
        const fps = data.fps || 0;
        const eta = data.eta || '--:--';

        document.getElementById('fileProgressFill').style.width = `${progress}%`;

        const displayName = data.filename && data.filename.length > 60
            ? data.filename.substring(0, 57) + '...'
            : (data.filename || 'File');

        let text = `Encoding: ${displayName} | ${progress.toFixed(1)}% | FPS: ${fps.toFixed(0)} | ETA: ${eta}`;

        if (this.encodingLogState.totalFiles > 1 && data.batch_eta) {
            text += ` | Batch ETA: ${data.batch_eta} (${this.encodingLogState.currentFile}/${this.encodingLogState.totalFiles})`;
            document.getElementById('batchProgressFill').style.width = `${data.batch_progress || 0}%`;
        }

        document.getElementById('fileProgressLabel').textContent = text;
    }

    updateStatistics() {
        const stats = this.encodingLogState;
        if (stats.fileStats.length === 0) return;

        const numFiles = stats.fileStats.length;
        const origSize = stats.totalOriginalSize / (1024 * 1024);
        const encSize = stats.totalEncodedSize / (1024 * 1024);
        const origUnit = origSize > 974 ? 'GB' : 'MB';
        const encUnit = encSize > 974 ? 'GB' : 'MB';
        const origValue = origSize > 974 ? origSize / 1024 : origSize;
        const encValue = encSize > 974 ? encSize / 1024 : encSize;

        const reduction = ((stats.totalOriginalSize - stats.totalEncodedSize) / stats.totalOriginalSize) * 100;
        const avgReduction = stats.fileStats.reduce((a, b) => a + b.reduction, 0) / numFiles;

        const text = `<b>Files Processed:</b> ${numFiles} | ` +
            `<b>Total Original:</b> ${origValue.toFixed(2)} ${origUnit} | <b>Encoded:</b> ${encValue.toFixed(2)} ${encUnit}<br>` +
            `<b>Overall Space Change:</b> ${reduction > 0 ? '-' : '+'}${Math.abs(reduction).toFixed(2)}% | ` +
            `<b>Average per File:</b> ${avgReduction > 0 ? '-' : '+'}${Math.abs(avgReduction).toFixed(2)}%`;

        document.getElementById('statisticsLabel').innerHTML = text;
    }

    async loadMedia() {
        let return_result = null;
        try {
            const result = await Utils.API.scanMedia();
            this.mediaFiles = result.files || [];
            return_result = [...this.mediaFiles];
            // If no files found, suggest scanning
            if (this.mediaFiles.length === 0) {
                Utils.Logger.info('No media files found. Click "Scan Media" to scan your media directory.');
                this.displayLog();
            } else {
                Utils.Logger.info(`Loaded ${this.mediaFiles.length} media files`);
            }

            this.filteredFiles = [...this.mediaFiles];
            this.renderMediaTable();
        } catch (error) {
            console.error('Failed to load media:', error);
            Utils.Logger.error(`Failed to load media files: ${error.message}`);
            this.displayLog();
        }
        return return_result;
    }

    async scanMedia() {
        const scanBtn = document.getElementById('scanBtn');
        const wasDisabled = scanBtn.disabled;
        scanBtn.disabled = true;

        try {
            Utils.Logger.info('Starting media scan...');
            this.displayLog();
            const result = await Utils.API.scanMedia();
            this.mediaFiles = result.files || [];
            console.log(this.mediaFiles);
            this.filteredFiles = this.mediaFiles;
            this.renderMediaTable();

            Utils.Logger.success(`Scan complete: ${this.mediaFiles.length} files found`);
            this.displayLog();
        } catch (error) {
            console.error('Scan failed:', error);
            Utils.Logger.error(`Scan failed: ${error.message}`);
            this.displayLog();
        } finally {
            scanBtn.disabled = wasDisabled;
        }
    }

    toggleLog() {
        const logSection = document.getElementById('logSection');
        const logDiv = document.getElementById('encodingLog');
        const header = logSection.querySelector('.section-header h2');
        const toggle = header.querySelector('.log-toggle');

        logSection.classList.toggle('collapsed');

        if (logSection.classList.contains('collapsed')) {
            this.logVisible = false;
            logDiv.classList.remove('visible');
            if (toggle) toggle.textContent = '▶';
        } else {
            this.logVisible = true;
            logDiv.classList.add('visible');
            if (toggle) toggle.textContent = '▼';
        }
    }

    toggleTheme() {
        const root = document.documentElement;
        const currentTheme = root.getAttribute('data-theme') || 'dark';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

        root.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);

        // Update button text
        const themeBtn = document.getElementById('themeBtn');
        themeBtn.textContent = newTheme === 'dark' ? '☀️' : '🌙';
    }

    groupMediaByShow() {
        //*Group media files hierarchically: Category -> Show -> Season"""
        this.groupedFiles = {};
        const shows = {};
        const movies = [];
        // Use a normalized-key map for extras to avoid duplicate groups
        const extras = {}; // normalizedKey -> array of files
        const extrasDisplayNames = {}; // normalizedKey -> displayName
        // Store metadata for group status (compliance counts)
        this.groupMetadata = {};

        this.filteredFiles.forEach(file => {
            if (file.category === 'extra') {
                // Group extras by their associated show (normalize to avoid duplicates)
                const rawName = (file.show_name && String(file.show_name).trim()) ? String(file.show_name).trim() : 'Other Extras';
                // Normalize: Unicode normalization, remove invisible/non-breaking spaces, collapse whitespace, lowercase
                const norm = rawName
                    .normalize('NFKC')
                    .replace(/[\u00A0\u200B\uFEFF]/g, ' ')
                    .replace(/\s+/g, ' ')
                    .trim()
                    .toLowerCase();
                if (!extras[norm]) {
                    extras[norm] = [];
                }
                extras[norm].push(file);
                // Preserve a display name for this normalized key
                if (!extrasDisplayNames[norm]) {
                    extrasDisplayNames[norm] = rawName.replace(/\s+/g, ' ').trim();
                }
            } else if (file.is_show && file.show_name) {
                // TV Show
                const showKey = file.show_name;
                if (!shows[showKey]) {
                    shows[showKey] = {};
                }

                const seasonKey = file.season || 'Unknown Season';
                if (!shows[showKey][seasonKey]) {
                    shows[showKey][seasonKey] = [];
                }

                shows[showKey][seasonKey].push(file);
            } else {
                // Movie
                movies.push(file);
            }
        });

        // Build hierarchical structure
        if (Object.keys(shows).length > 0) {
            this.groupedFiles['Shows'] = shows;
            // Auto-collapse all shows and their seasons
            Object.keys(shows).forEach(showName => {
                const showKey = `Shows-${showName}`;
                this.collapsedGroups.add(showKey);
                // Calculate compliance status for this show
                const showFiles = Object.values(shows[showName]).flat();
                this.groupMetadata[showKey] = this._calculateGroupStatus(showFiles);
                // Also auto-collapse all seasons in this show
                Object.keys(shows[showName]).forEach(seasonName => {
                    const seasonKey = `Shows-${showName}-${seasonName}`;
                    this.collapsedGroups.add(seasonKey);
                    // Calculate compliance status for this season
                    const seasonFiles = shows[showName][seasonName];
                    this.groupMetadata[seasonKey] = this._calculateGroupStatus(seasonFiles);
                });
            });
        }
        if (movies.length > 0) {
            this.groupedFiles['Movies'] = { 'Movies': movies };
        }
        if (Object.keys(extras).length > 0) {
            // Convert normalized extras map to display-keyed object for rendering
            const extrasDisplay = {};
            Object.keys(extras).forEach(normKey => {
                const displayName = extrasDisplayNames[normKey] || normKey;
                extrasDisplay[displayName] = extras[normKey];
            });

            this.groupedFiles['Extras'] = extrasDisplay;
            // Calculate compliance status for extras groups (use display keys)
            Object.keys(extrasDisplay).forEach(extraGroup => {
                const extraKey = `Extras-${extraGroup}`;
                this.collapsedGroups.add(extraKey);
                this.groupMetadata[extraKey] = this._calculateGroupStatus(extrasDisplay[extraGroup]);
            });
        }
    }

    _calculateGroupStatus(files) {
        /**Calculate compliance status for a group of files.
         * Returns object with counts and status text.
         */
        if (!files || files.length === 0) return { needsEncoding: 0, compliant: 0, statusText: '' };

        // Status values from MediaStatus enum: "✅", "⚠️", "ℹ️", "🔍", "⛔", "❔"
        const needsEncoding = files.filter(f => f.status === '⚠️' || f.status === 'NEEDS_REENCODING').length;
        const belowStandard = files.filter(f => f.status === 'ℹ️' || f.status === 'BELOW_STANDARD').length;
        const compliant = files.filter(f => f.status === '✅' || f.status === 'COMPLIANT').length;

        let statusText = '';
        if (needsEncoding === 0) {
            statusText = ' - ✅';
        } else {
            statusText = ` - ⚠️ ${needsEncoding}`;
        }

        return { needsEncoding, compliant, statusText };
    }

    renderMediaTable() {
        const tbody = document.getElementById('mediaTableBody');

        if (this.filteredFiles.length === 0) {
            tbody.innerHTML = '<tr class="loading-row"><td colspan="9">No media files found</td></tr>';
            return;
        }

        // Group files for display
        this.groupMediaByShow();

        let html = '';

        // Render hierarchical structure: Category -> Show -> Season -> Files
        Object.entries(this.groupedFiles).forEach(([categoryName, showsOrFiles]) => {
            const categoryKey = categoryName;
            const isCategoryCollapsed = this.collapsedGroups.has(categoryKey);

            // Category header (Shows, Movies, Extras)
            html += `
                <tr class="group-header category-header ${isCategoryCollapsed ? 'collapsed' : ''}" data-group="${categoryKey}" onclick="app.toggleGroup('${categoryKey}')">
                    <td colspan="9">
                        <span class="expand-toggle" style="margin-right: 0.5rem;">${isCategoryCollapsed ? '▶' : '▼'}</span>
                        <strong>${categoryName}</strong>
                    </td>
                </tr>
            `;

            // If category is collapsed, we still need to render the contents but mark them as hidden
            const isCategoryHidden = isCategoryCollapsed;

            // Handle Extras separately (group by show name, no season layer)
            if (categoryName === 'Extras') {
                Object.entries(showsOrFiles).forEach(([groupName, files]) => {
                    const groupKey = `${categoryName}-${groupName}`;
                    const isGroupCollapsed = this.collapsedGroups.has(groupKey);

                    // Group header with checkbox and compliance status
                    const groupSelectedCount = files.filter(f => this.selectedFiles.has(f.path)).length;
                    const groupChecked = groupSelectedCount === files.length && files.length > 0;
                    const groupStatus = this.groupMetadata[groupKey] || { statusText: '' };

                    html += `
                        <tr class="group-header extras-header ${isGroupCollapsed ? 'collapsed' : ''} ${isCategoryHidden ? 'hidden' : ''}" data-group="${groupKey}">
                            <td colspan="9">
                                <input type="checkbox"
                                       class="group-checkbox extras-checkbox"
                                       data-group="${groupKey}"
                                       ${groupChecked ? 'checked' : ''}
                                       onclick="event.stopPropagation(); app.toggleGroupSelection(event)"
                                       style="margin-right: 0.5rem;">
                                <span class="expand-toggle" style="margin-right: 0.5rem;" onclick="app.toggleGroup('${groupKey}')">${isGroupCollapsed ? '▶' : '▼'}</span>
                                ${Utils.escapeHtml(groupName)}${groupStatus.statusText}
                                <span class="file-count">(${files.length} files)</span>
                            </td>
                        </tr>
                    `;

                    // File rows - add hidden class if group is collapsed
                    html += files.map((file) => {
                        const fileRow = this.renderFileRow(file, groupKey);
                        const hiddenClass = (isGroupCollapsed || isCategoryHidden) ? ' hidden' : '';
                        return fileRow.replace('<tr class="media-row group-child', `<tr class="media-row group-child${hiddenClass}`);
                    }).join('');
                });
            } else {
                // Process Shows and Movies normally
                Object.entries(showsOrFiles).forEach(([showName, seasonsOrFiles]) => {
                    // Only show show headers for actual shows (not for Movies/Extras)
                    const isShowCategory = categoryName === 'Shows' && showName !== 'Movies' && showName !== 'Extras';

                    if (isShowCategory) {
                        const showKey = `${categoryName}-${showName}`;
                        const isShowCollapsed = this.collapsedGroups.has(showKey);

                        // Calculate show selection state
                        const showFiles = Object.values(seasonsOrFiles).flat();
                        const showSelectedCount = showFiles.filter(f => this.selectedFiles.has(f.path)).length;
                        const showChecked = showSelectedCount === showFiles.length && showFiles.length > 0;
                        const showIndeterminate = showSelectedCount > 0 && showSelectedCount < showFiles.length;

                        // Show header with checkbox and compliance status
                        const showStatus = this.groupMetadata[showKey] || { statusText: '' };
                        html += `
                            <tr class="group-header show-header ${isShowCollapsed ? 'collapsed' : ''} ${isCategoryHidden ? 'hidden' : ''}" data-group="${showKey}">
                                <td colspan="9">
                                    <input type="checkbox"
                                           class="group-checkbox show-checkbox"
                                           data-group="${showKey}"
                                           ${showChecked ? 'checked' : ''}
                                           onclick="event.stopPropagation(); app.toggleGroupSelection(event)"
                                           style="margin-right: 0.5rem;">
                                    <span class="expand-toggle" style="margin-right: 0.5rem;" onclick="app.toggleGroup('${showKey}')">${isShowCollapsed ? '▶' : '▼'}</span>
                                    ${Utils.escapeHtml(showName)}${showStatus.statusText}
                                </td>
                            </tr>
                        `;

                        // Always render seasons and files but mark them as hidden if the show is collapsed
                        // Process seasons for this show
                        Object.entries(seasonsOrFiles).forEach(([seasonName, files]) => {
                            const seasonKey = `${categoryName}-${showName}-${seasonName}`;
                            const isSeasonCollapsed = this.collapsedGroups.has(seasonKey);

                            // Calculate season selection state
                            const seasonSelectedCount = files.filter(f => this.selectedFiles.has(f.path)).length;
                            const seasonChecked = seasonSelectedCount === files.length && files.length > 0;
                            const seasonIndeterminate = seasonSelectedCount > 0 && seasonSelectedCount < files.length;

                            // Season header with checkbox and compliance status - add hidden class if parent show is collapsed
                            const seasonStatus = this.groupMetadata[seasonKey] || { statusText: '' };
                            html += `
                                <tr class="group-header season-header ${isSeasonCollapsed ? 'collapsed' : ''} ${isShowCollapsed || isCategoryHidden ? 'hidden' : ''}" data-group="${seasonKey}">
                                    <td colspan="9">
                                        <input type="checkbox"
                                               class="group-checkbox season-checkbox"
                                               data-group="${seasonKey}"
                                               ${seasonChecked ? 'checked' : ''}
                                               onclick="event.stopPropagation(); app.toggleGroupSelection(event)"
                                               style="margin-right: 0.5rem;">
                                        <span class="expand-toggle" style="margin-right: 0.5rem;" onclick="app.toggleGroup('${seasonKey}')">${isSeasonCollapsed ? '▶' : '▼'}</span>
                                        Season ${Utils.escapeHtml(seasonName)}${seasonStatus.statusText}
                                        <span class="file-count">(${files.length} files)</span>
                                    </td>
                                </tr>
                            `;

                            // File rows - add hidden class if show is collapsed or season is collapsed
                            html += files.map((file) => {
                                const fileRow = this.renderFileRow(file, seasonKey);
                                // Add hidden class to file rows if parent show or season is collapsed
                                const hiddenClass = (isShowCollapsed || isSeasonCollapsed || isCategoryHidden) ? ' hidden' : '';
                                return fileRow.replace('<tr class="media-row group-child', `<tr class="media-row group-child${hiddenClass}`);
                            }).join('');
                        });
                    } else {
                        // Movies or other categories - handle flat lists
                        if (Array.isArray(seasonsOrFiles)) {
                            // Flat list (Movies)
                            html += seasonsOrFiles.map((file) => this.renderFileRow(file, categoryKey)).join('');
                        }
                    }
                });
            }
        });

        tbody.innerHTML = html;

        // Re-attach event listeners for checkboxes
        document.querySelectorAll('.media-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => this.toggleFileSelection(e));
        });

        // Attach event listeners for group checkboxes
        document.querySelectorAll('.group-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => this.toggleGroupSelection(e));
        });
    }

    toggleGroupSelection(event) {
        const checkbox = event.target;
        const groupKey = checkbox.dataset.group;
        const isChecked = checkbox.checked;

        // Find all files that belong to this group
        const rowsInGroup = document.querySelectorAll(`.group-child[data-group="${groupKey}"]`);

        // Directly update checkboxes without triggering change events
        rowsInGroup.forEach(row => {
            const fileCheckbox = row.querySelector('.media-checkbox');
            if (fileCheckbox) {
                fileCheckbox.checked = isChecked;
                // Update selectedFiles directly
                if (isChecked) {
                    this.selectedFiles.add(fileCheckbox.dataset.path);
                } else {
                    this.selectedFiles.delete(fileCheckbox.dataset.path);
                }
            }
        });

        // If this is a show checkbox, also handle child season checkboxes
        if (checkbox.classList.contains('show-checkbox')) {
            const seasonCheckboxes = document.querySelectorAll(`.season-checkbox[data-group^="${groupKey}-"]`);
            seasonCheckboxes.forEach(seasonCheckbox => {
                seasonCheckbox.checked = isChecked;
            });
        }

        // Update select all checkbox state
        this.updateSelectAllCheckbox();
    }

    renderFileRow(file, groupKey) {
        const isSelected = this.selectedFiles.has(file.path);

        return `
            <tr class="media-row group-child" data-group="${groupKey}">
                <td>
                    <input type="checkbox"
                           class="media-checkbox"
                           data-path="${file.path}"
                           ${isSelected ? 'checked' : ''}
                           onchange="app.toggleFileSelection(event)">
                </td>
                <td>${Utils.escapeHtml(file.filename)}</td>
                <td><span class="status-icon">${file.status}</span></td>
                <td>${file.resolution || 'Unknown'}</td>
                <td>${file.codec || 'Unknown'}</td>
                <td>${file.bitrate ? Utils.formatBitrate(file.bitrate) : '-'}</td>
                <td>${file.duration ? Utils.formatDuration(file.duration) : '-'}</td>
                <td>${file.file_size ? Utils.formatFileSize(file.file_size) : '-'}</td>
                <td>${file.category}</td>
            </tr>
        `;
    }

    toggleGroup(groupKey) {
        if (this.collapsedGroups.has(groupKey)) {
            this.collapsedGroups.delete(groupKey);
        } else {
            this.collapsedGroups.add(groupKey);
        }

        const isNowCollapsed = this.collapsedGroups.has(groupKey);
        const headerRow = document.querySelector(`.group-header[data-group="${groupKey}"]`);

        // Update header appearance
        if (headerRow) {
            headerRow.classList.toggle('collapsed');
            const toggle = headerRow.querySelector('.expand-toggle');
            if (toggle) {
                toggle.textContent = isNowCollapsed ? '▶' : '▼';
            }
        }

        // Handle collapsing children when parent is collapsed
        if (isNowCollapsed) {
            // When collapsing a parent, hide all direct children
            const childRows = document.querySelectorAll(`.group-child[data-group="${groupKey}"]`);
            childRows.forEach(row => {
                if (!row.classList.contains('hidden')) {
                    row.classList.add('hidden');
                }
            });

            // Also hide child group headers that belong to this parent
            const allHeaders = document.querySelectorAll(`.group-header[data-group^="${groupKey}-"]`);
            allHeaders.forEach(header => {
                if (!header.classList.contains('hidden')) {
                    header.classList.add('hidden');
                }
                // Hide their children too
                const headerGroupKey = header.getAttribute('data-group');
                const grandchildRows = document.querySelectorAll(`.group-child[data-group="${headerGroupKey}"]`);
                grandchildRows.forEach(row => {
                    if (!row.classList.contains('hidden')) {
                        row.classList.add('hidden');
                    }
                });
            });
        } else {
            // When expanding, show direct children and headers ONLY if their parent is not collapsed
            const childRows = document.querySelectorAll(`.group-child[data-group="${groupKey}"]`);
            childRows.forEach(row => {
                row.classList.remove('hidden');
            });

            const childHeaders = document.querySelectorAll(`.group-header[data-group^="${groupKey}-"]`);
            childHeaders.forEach(header => {
                const headerGroupKey = header.getAttribute('data-group');

                // Check if this header's parent is collapsed
                // For season headers like "Shows-ShowName-Season1", the parent is "Shows-ShowName"
                const parts = headerGroupKey.split('-');
                let parentKey = null;

                if (parts.length === 3) {
                    // This is a season header, parent is the show
                    parentKey = parts.slice(0, 2).join('-');
                } else if (parts.length === 2) {
                    // This is a group header (show/extra), parent is the category
                    parentKey = parts[0];
                }

                // Only show the header if its parent is not collapsed
                if (parentKey && !this.collapsedGroups.has(parentKey)) {
                    header.classList.remove('hidden');
                }
            });
        }
    }


    toggleFileSelection(event) {
        const path = event.target.dataset.path;

        if (event.target.checked) {
            this.selectedFiles.add(path);
        } else {
            this.selectedFiles.delete(path);
        }

        // Update select all checkbox
        this.updateSelectAllCheckbox();
    }

    updateGroupCheckboxes() {
        // Update all show checkboxes
        document.querySelectorAll('.show-checkbox').forEach(showCheckbox => {
            const groupKey = showCheckbox.dataset.group;
            const filesInGroup = document.querySelectorAll(`.group-child[data-group^="${groupKey}"]`);
            const filesInGroupArray = Array.from(filesInGroup).map(row => row.querySelector('.media-checkbox')?.dataset.path).filter(Boolean);

            const selectedCount = filesInGroupArray.filter(path => this.selectedFiles.has(path)).length;
            showCheckbox.checked = selectedCount === filesInGroupArray.length && filesInGroupArray.length > 0;
            showCheckbox.indeterminate = selectedCount > 0 && selectedCount < filesInGroupArray.length;
        });

        // Update all season checkboxes
        document.querySelectorAll('.season-checkbox').forEach(seasonCheckbox => {
            const groupKey = seasonCheckbox.dataset.group;
            const filesInGroup = document.querySelectorAll(`.group-child[data-group="${groupKey}"]`);
            const filesInGroupArray = Array.from(filesInGroup).map(row => row.querySelector('.media-checkbox')?.dataset.path).filter(Boolean);

            const selectedCount = filesInGroupArray.filter(path => this.selectedFiles.has(path)).length;
            seasonCheckbox.checked = selectedCount === filesInGroupArray.length && filesInGroupArray.length > 0;
            seasonCheckbox.indeterminate = selectedCount > 0 && selectedCount < filesInGroupArray.length;
        });

        // Update all extras checkboxes
        document.querySelectorAll('.extras-checkbox').forEach(extrasCheckbox => {
            const groupKey = extrasCheckbox.dataset.group;
            const filesInGroup = document.querySelectorAll(`.group-child[data-group="${groupKey}"]`);
            const filesInGroupArray = Array.from(filesInGroup).map(row => row.querySelector('.media-checkbox')?.dataset.path).filter(Boolean);

            const selectedCount = filesInGroupArray.filter(path => this.selectedFiles.has(path)).length;
            extrasCheckbox.checked = selectedCount === filesInGroupArray.length && filesInGroupArray.length > 0;
            extrasCheckbox.indeterminate = selectedCount > 0 && selectedCount < filesInGroupArray.length;
        });
    }

    toggleSelectAll(event) {
        if (event.target.checked) {
            this.selectAll();
        } else {
            this.deselectAll();
        }
    }

    selectAll() {
        this.filteredFiles.forEach(file => {
            this.selectedFiles.add(file.path);
        });
        document.getElementById('selectAllCheckbox').checked = true;
        this.renderMediaTable();
    }

    deselectAll() {
        this.selectedFiles.clear();
        document.getElementById('selectAllCheckbox').checked = false;
        this.renderMediaTable();
    }

    updateSelectAllCheckbox() {
        const checkbox = document.getElementById('selectAllCheckbox');
        const filteredCount = this.filteredFiles.length;
        const selectedFromFiltered = this.filteredFiles.filter(f => this.selectedFiles.has(f.path)).length;

        if (filteredCount === 0) {
            checkbox.checked = false;
            checkbox.indeterminate = false;
        } else if (selectedFromFiltered === filteredCount) {
            checkbox.checked = true;
            checkbox.indeterminate = false;
        } else if (selectedFromFiltered > 0) {
            checkbox.checked = false;
            checkbox.indeterminate = true;
        } else {
            checkbox.checked = false;
            checkbox.indeterminate = false;
        }
    }

    filterMedia(query) {
        const searchTerm = query.toLowerCase();
        const statusFilter = document.getElementById('filterStatus').value;

        this.filteredFiles = this.mediaFiles.filter(file => {
            const matchesSearch = file.filename.toLowerCase().includes(searchTerm);
            const matchesStatus = !statusFilter || file.status === statusFilter;
            return matchesSearch && matchesStatus;
        });

        this.updateSelectAllCheckbox();
        this.renderMediaTable();
    }

    filterByStatus(status) {
        const searchQuery = document.getElementById('searchInput').value;
        this.filterMedia(searchQuery);
    }

    async startEncoding() {
        console.log('startEncoding called');
        try {
            if (this.selectedFiles.size === 0) {
                console.log('No files selected');
                await Dialogs.alert('No Files Selected', 'Please select at least one file to encode');
                return;
            }

            const count = this.selectedFiles.size;
            console.log('Selected files count:', count);
            const confirmed = await Dialogs.confirm(
                'Start Encoding',
                `Encode ${count} selected file(s)?`
            );

            if (!confirmed) {
                console.log('User cancelled confirm dialog');
                return;
            }

            // Detect resolutions in selected files
            const resolutionsInBatch = new Set();
            this.mediaFiles.forEach(file => {
                if (this.selectedFiles.has(file.path) && file.resolution) {
                    // Normalize resolution to standard bucket (e.g., "1080p", "720p", "4k")
                    const res = file.resolution.toLowerCase().trim();

                    if (res.includes('2160') || res.includes('4k')) {
                        resolutionsInBatch.add('4k');
                    } else if (res.includes('1440')) {
                        resolutionsInBatch.add('1440p');
                    } else if (res.includes('1080')) {
                        resolutionsInBatch.add('1080p');
                    } else if (res.includes('720')) {
                        resolutionsInBatch.add('720p');
                    } else {
                        resolutionsInBatch.add('low_res');
                    }
                }
            });

            console.log('Resolutions in batch:', Array.from(resolutionsInBatch));

            // Show encoding settings dialog
            const encodingDialog = new EncodingSettingsDialog(Array.from(resolutionsInBatch));
            console.log('EncodingSettingsDialog created with resolutions:', resolutionsInBatch);
            const encodingSettings = await encodingDialog.show();
            console.log('Encoding settings returned:', encodingSettings);

            if (!encodingSettings) {
                console.log('User cancelled encoding settings dialog');
                return;  // User cancelled
            }

            document.getElementById('encodeBtn').disabled = true;
            Utils.Logger.info(`Starting encoding of ${count} files with settings: ${JSON.stringify(encodingSettings)}`);
            this.displayLog();

            const result = await Utils.API.startEncoding(Array.from(this.selectedFiles), encodingSettings);
            console.log('Encoding started:', result);

            this.isEncoding = true;
            document.getElementById('stopEncodingBtn').disabled = false;

            Utils.Logger.success(result.message);
            this.displayLog();
        } catch (error) {
            console.error('Failed to start encoding:', error);
            Utils.Logger.error(`Failed to start encoding: ${error.message}`);
            this.displayLog();
            await Dialogs.alert('Encoding Error', error.message);
        } finally {
            document.getElementById('encodeBtn').disabled = false;
        }
    }

    async stopEncoding() {
        const confirmed = await Dialogs.confirm('Stop Encoding', 'Stop the current encoding process?');

        if (!confirmed) return;

        // Immediately disable the button to prevent multiple clicks
        const stopBtn = document.getElementById('stopEncodingBtn');
        stopBtn.disabled = true;
        stopBtn.textContent = 'Stopping...';

        try {
            await Utils.API.stopEncoding();
            // Set encoding to false immediately
            this.isEncoding = false;
            Utils.Logger.warning('Encoding stopped by user');
            this.displayLog();
        } catch (error) {
            console.error('Failed to stop encoding:', error);
            Utils.Logger.error(`Failed to stop encoding: ${error.message}`);
            this.displayLog();
            // Re-enable button if there was an error
            stopBtn.disabled = false;
            stopBtn.textContent = 'Stop Encoding';
        }
    }

    addLogEntry(data) {
        Utils.Logger.add(data.log_type || 'info', data.message, data.color);
        this.displayLog();
    }

    displayLog() {
        const logDiv = document.getElementById('encodingLog');
        const logSection = document.getElementById('logSection');
        const header = logSection.querySelector('.section-header h2');
        let toggle = header.querySelector('.log-toggle');

        // Add toggle indicator if not present
        if (!toggle) {
            toggle = document.createElement('span');
            toggle.className = 'log-toggle';
            toggle.textContent = logSection.classList.contains('collapsed') ? '▶' : '▼';
            header.prepend(toggle);
        }

        // Update log content
        logDiv.innerHTML = Utils.Logger.logs
            .map(entry => entry.html)
            .join('');

        // Auto-show log when there's content
        if (Utils.Logger.logs.length > 0 && logSection.classList.contains('collapsed')) {
            this.logVisible = true;
            logDiv.classList.add('visible');
            logSection.classList.remove('collapsed');
            toggle.textContent = '▼';
        }

        // Auto-scroll to bottom
        logDiv.scrollTop = logDiv.scrollHeight;
    }

    clearLog() {
        Utils.Logger.clear();
        this.displayLog();
    }
}

// Initialize app when DOM is ready
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new OpenMediaManager();
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (app && app.logWebSocket) {
        app.logWebSocket.close();
    }
});
