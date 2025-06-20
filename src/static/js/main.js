// Main JavaScript for Image Processor Web

// Global variables for presets
let cityPresets = {
    version: '1.0',
    presets: []
};

let clientPresets = {
    version: '1.0',
    presets: []
};

// Variable to store selected files for geotagging, including their paths
let selectedGeotaggingFiles = [];

// Global variable to store hierarchical city preset data
let cityPresetsData = {};

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap components
    initializeBootstrapComponents();
    
    // Initialize navigation
    initializeNavigation();
    
    // Initialize file upload areas
    initializeFileUploads();
    
    // Initialize form handlers
    initializeFormHandlers();
    
    // Initialize preset managers
    initializePresetManagers();
    
    // Load presets
    loadCityPresets();
    loadClientPresets();
});

// Initialize Bootstrap components
function initializeBootstrapComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

// Initialize navigation
function initializeNavigation() {
    const navLinks = document.querySelectorAll('.sidebar .nav-link');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all links
            navLinks.forEach(l => l.classList.remove('active'));
            
            // Add active class to clicked link
            this.classList.add('active');
            
            // Hide all content sections
            document.querySelectorAll('.content-section').forEach(section => {
                section.classList.remove('active');
            });
            
            // Show the selected content section
            const sectionId = this.getAttribute('data-section') + '-section';
            document.getElementById(sectionId).classList.add('active');
        });
    });
}

// Initialize file upload areas
function initializeFileUploads() {
    // Geotagging file upload
    initializeFileUpload('upload-area', 'file-input', 'file-list', 'file-list-container', 'geotagging');
    
    // Conversion file upload
    initializeFileUpload('conversion-upload-area', 'conversion-file-input', 'conversion-file-list', 'conversion-file-list-container', 'conversion');
    
    // Resizing file upload
    initializeFileUpload('resizing-upload-area', 'resizing-file-input', 'resizing-file-list', 'resizing-file-list-container', 'resizing');
    
    // Watermark file upload
    initializeFileUpload('watermark-upload-area', 'watermark-file-input', 'watermark-file-list', 'watermark-file-list-container', 'watermark');
}

// Initialize a single file upload area
function initializeFileUpload(areaId, inputId, listId, containerId, section) {
    const uploadArea = document.getElementById(areaId);
    const fileInput = document.getElementById(inputId);
    const fileList = document.getElementById(listId);
    const fileListContainer = document.getElementById(containerId);
    
    if (!uploadArea || !fileInput || !fileList || !fileListContainer) {
        console.error(`Missing elements for file upload: ${areaId}, ${inputId}, ${listId}, ${containerId}`);
        return;
    }
    
    // Handle drag and drop events
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('border-primary');
    });
    
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('border-primary');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('border-primary');
        
        if (e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files, fileList, fileListContainer, section);
        }
    });
    
    // Handle file input change
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            handleFiles(this.files, fileList, fileListContainer, section);
        }
    });
}

// Handle selected files
function handleFiles(files, fileList, fileListContainer, section) {
    // Clear existing file list and selected files array for this section
    fileList.innerHTML = '';
    if (section === 'geotagging') {
        selectedGeotaggingFiles = [];
    }
    
    // Group files by their directory
    const filesByDirectory = {};
    
    // Add each file to the list and selected files array
    Array.from(files).forEach(file => {
        // Ensure we have a valid File object and it's not a directory (though webkitdirectory usually handles this)
        if (file instanceof File) {
            const filePath = file.webkitRelativePath || file.name;
            const directory = filePath.split('/').slice(0, -1).join('/');
            
            if (!filesByDirectory[directory]) {
                filesByDirectory[directory] = [];
            }
            filesByDirectory[directory].push(file);

            // Log details for single file case debugging
            if (files.length === 1 && section === 'geotagging') {
                 console.log('Handling single file from folder:', {
                     name: file.name,
                     size: file.size,
                     type: file.type,
                     lastModified: file.lastModified,
                     webkitRelativePath: file.webkitRelativePath
                 });
            }
            
        } else {
            console.warn('Skipping item that is not a File object:', file);
        }
    });
    
    // Create directory structure in the list
    Object.entries(filesByDirectory).forEach(([directory, files]) => {
        // Create directory header if not root
        if (directory) {
            const dirHeader = document.createElement('li');
            dirHeader.className = 'list-group-item bg-light';
            dirHeader.innerHTML = `<i class="bi bi-folder"></i> ${directory}`;
            fileList.appendChild(dirHeader);
        }
        
        // Add files in this directory
        files.forEach(file => {
            const listItem = document.createElement('li');
            listItem.className = 'list-group-item';
            
            // Display file name with proper indentation if in subdirectory
            const fileNameDisplay = document.createElement('span');
            fileNameDisplay.textContent = file.webkitRelativePath || file.name;
            
            const fileSize = document.createElement('span');
            fileSize.className = 'text-muted ms-2';
            // Display 0 Bytes if size is 0, which might indicate a reading issue
            fileSize.textContent = file.size === 0 ? '0 Bytes (Potential Issue)' : formatFileSize(file.size);
            
            const removeButton = document.createElement('i');
            removeButton.className = 'bi bi-x-circle file-remove';
            removeButton.addEventListener('click', function() {
                // Remove from display
                listItem.remove();
                
                // Remove from selected files array
                if (section === 'geotagging') {
                    const index = selectedGeotaggingFiles.findIndex(item => item.file === file);
                    if (index > -1) {
                        selectedGeotaggingFiles.splice(index, 1);
                    }
                }
                
                // Hide the file list container if no files are left
                if (fileList.children.length === 0) {
                    fileListContainer.classList.add('d-none');
                }
            });
            
            listItem.appendChild(fileNameDisplay);
            listItem.appendChild(fileSize);
            listItem.appendChild(removeButton);
            
            fileList.appendChild(listItem);
            
            // Add to selected files array with path, only if it's a valid File with size > 0
             if (section === 'geotagging' && file.size > 0) {
                selectedGeotaggingFiles.push({ 
                    file: file, 
                    path: file.webkitRelativePath || file.name 
                });
            } else if (section === 'geotagging' && file.size === 0) {
                 console.warn('Skipping file with 0 size from selectedGeotaggingFiles:', file.name);
            }
        });
    });
    
    // Show the file list container if there are files with size > 0
     if (selectedGeotaggingFiles.length > 0) {
        fileListContainer.classList.remove('d-none');
    } else {
         fileListContainer.classList.add('d-none');
    }
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Initialize form handlers
function initializeFormHandlers() {
    // Geotagging form
    initializeGeotaggingForm();
    
    // Conversion form
    initializeConversionForm();
    
    // Resizing form
    initializeResizingForm();
    
    // Watermark form
    initializeWatermarkForm();
}

// Initialize geotagging form
function initializeGeotaggingForm() {
    const form = document.getElementById('geotagging-form');
    const clearButton = document.getElementById('clear-button');
    const cityPresetSelect = document.getElementById('city-preset');
    const clientPresetSelect = document.getElementById('client-preset');
    const datetimeInput = document.getElementById('datetime');
    
    // Cache relevant elements for geotagging form
    const cityPresetCountrySelect = document.getElementById('cityPresetCountrySelect');
    const cityPresetStateProvinceSelect = document.getElementById('cityPresetStateProvinceSelect');

    // Set current datetime for the datetime input
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    datetimeInput.value = now.toISOString().slice(0, 16);

    // Event listener for city preset dropdown
    cityPresetSelect.addEventListener('change', function() {
        const selectedCityId = this.value;
        const selectedCountry = cityPresetCountrySelect.value;
        const selectedState = cityPresetStateProvinceSelect.value;
        
        const latitudeInput = document.getElementById('latitude');
        const longitudeInput = document.getElementById('longitude');

        if (selectedCityId && selectedCountry && selectedState && cityPresetsData[selectedCountry] && cityPresetsData[selectedCountry][selectedState]) {
            const selectedCity = cityPresetsData[selectedCountry][selectedState].find(city => city.id === selectedCityId);
            if (selectedCity) {
                latitudeInput.value = selectedCity.center.lat.toFixed(6);
                longitudeInput.value = selectedCity.center.lng.toFixed(6);
                // Automatically enable random coordinates when a city preset is selected
                latitudeInput.dataset.useRandom = 'true';
                // Set location fields from city preset
                if (document.getElementById('sublocation')) {
                    document.getElementById('sublocation').value = selectedCity.sublocation || '';
                }
            }
        } else {
            // If no city preset is selected, clear coordinates and disable random coordinates
            latitudeInput.value = '';
            longitudeInput.value = '';
            latitudeInput.dataset.useRandom = 'false';
        }
    });

    // Event listener for country select in city presets
    cityPresetCountrySelect.addEventListener('change', function() {
        loadStatesForCityPresets(this.value);
        // Reset city and coordinates when country changes
        document.getElementById('city-preset').value = '';
        document.getElementById('latitude').value = '';
        document.getElementById('longitude').value = '';
        document.getElementById('latitude').dataset.useRandom = 'false';
    });

    // Event listener for state/province select in city presets
    cityPresetStateProvinceSelect.addEventListener('change', function() {
        loadCitiesForCityPresets(cityPresetCountrySelect.value, this.value);
        // Reset city and coordinates when state/province changes
        document.getElementById('city-preset').value = '';
        document.getElementById('latitude').value = '';
        document.getElementById('longitude').value = '';
        document.getElementById('latitude').dataset.useRandom = 'false';
    });

    // Handle client preset change
    clientPresetSelect.addEventListener('change', function() {
        if (this.value) {
            const preset = clientPresets.presets.find(p => p.id === this.value);
            if (preset) {
                // Fill contact information
                if (preset.contact_info) {
                    if (preset.contact_info.byline) document.getElementById('creator').value = preset.contact_info.byline;
                    if (preset.contact_info.byline_title) document.getElementById('creator-title').value = preset.contact_info.byline_title;
                    if (preset.contact_info.address) document.getElementById('address').value = preset.contact_info.address;
                    if (preset.contact_info.city) document.getElementById('city').value = preset.contact_info.city;
                    if (preset.contact_info.state_province) document.getElementById('state').value = preset.contact_info.state_province;
                    if (preset.contact_info.postal_code) document.getElementById('postal-code').value = preset.contact_info.postal_code;
                    if (preset.contact_info.country) document.getElementById('country').value = preset.contact_info.country;
                    if (preset.contact_info.phone) document.getElementById('phone').value = preset.contact_info.phone;
                    if (preset.contact_info.email) document.getElementById('email').value = preset.contact_info.email;
                    if (preset.contact_info.url) document.getElementById('url').value = preset.contact_info.url;
                }
                // Keywords are directly on the preset object
                if (preset.keywords) document.getElementById('keywords').value = preset.keywords.join(', ');
            }
        }
    });
    
    // Handle form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const progressContainer = document.getElementById('progress-container');
        progressContainer.classList.remove('d-none');

        const formData = new FormData();

        // Append files and their original paths
        selectedGeotaggingFiles.forEach(item => {
            formData.append('files[]', item.file);
            formData.append('file_paths[]', item.path);
        });

        // Collect EXIF data
        const exifData = {};
        if (document.getElementById('latitude').value) exifData.GPSLatitude = parseFloat(document.getElementById('latitude').value);
        if (document.getElementById('longitude').value) exifData.GPSLongitude = parseFloat(document.getElementById('longitude').value);
        // Automatically set use_random_coordinates based on city preset selection
        if (document.getElementById('latitude').dataset.useRandom === 'true') {
            exifData.use_random_coordinates = true;
        }
        let selectedCity = null;
        if (cityPresetSelect.value) {
            selectedCity = findCityPreset(cityPresetSelect.value);
            exifData.preset = selectedCity;
            if (selectedCity && selectedCity.name) {
                exifData.CityDisplayName = selectedCity.name;
            }
        }
        if (datetimeInput.value) {
            const dt = new Date(datetimeInput.value);
            exifData.GPSDateStamp = dt.toISOString().slice(0, 10).replace(/-/g, ':');
            exifData.GPSTimeStamp = dt.toTimeString().slice(0, 8);
            exifData["XMP:GPSDateTime"] = dt.toISOString().slice(0, 19) + "Z";
        }
        if (document.getElementById('creator').value) exifData.Creator = document.getElementById('creator').value;
        if (document.getElementById('creator-title').value) exifData.CreatorTitle = document.getElementById('creator-title').value;
        if (document.getElementById('address').value) exifData.Address = document.getElementById('address').value;
        if (document.getElementById('city').value) exifData.City = document.getElementById('city').value;
        if (document.getElementById('cityPresetStateProvinceSelect').value) exifData.State = document.getElementById('cityPresetStateProvinceSelect').value;
        if (document.getElementById('postal-code').value) exifData.PostalCode = document.getElementById('postal-code').value;
        if (document.getElementById('cityPresetCountrySelect').value) exifData.Country = document.getElementById('cityPresetCountrySelect').value;
        if (document.getElementById('phone').value) exifData.Phone = document.getElementById('phone').value;
        if (document.getElementById('email').value) exifData.Email = document.getElementById('email').value;
        if (document.getElementById('url').value) {
            exifData.URL = document.getElementById('url').value;
            exifData.ContactURL = document.getElementById('url').value;
        }
        if (document.getElementById('keywords').value) exifData.Keywords = document.getElementById('keywords').value.split(',').map(k => k.trim()).filter(k => k);
        // Only assign contact fields from contact inputs
        if (document.getElementById('country').value) {
            exifData.ContactCountry = document.getElementById('country').value;
        }
        if (document.getElementById('state').value) {
            exifData.ContactState = document.getElementById('state').value;
        }
        if (document.getElementById('city').value) {
            exifData.ContactCity = document.getElementById('city').value;
        }

        formData.append('exif_data', JSON.stringify(exifData));
        formData.append('output_format', document.getElementById('output-format').value);

        try {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/geotagging/process', true);

            xhr.upload.onprogress = function(event) {
                if (event.lengthComputable) {
                    const percentComplete = (event.loaded / event.total) * 100;
                    document.getElementById('progress-bar').style.width = percentComplete + '%';
                    document.getElementById('progress-bar').textContent = Math.round(percentComplete) + '%';
                }
            };

            let pollProgressInterval = null;
            xhr.onreadystatechange = function() {
                if (xhr.readyState === XMLHttpRequest.DONE) {
                    if (xhr.status === 200) {
                        const response = JSON.parse(xhr.responseText);
                        window.lastGeotaggingSessionId = response.session_id;
                        
                        // Start polling for progress after receiving session_id
                        if (pollProgressInterval) {
                            clearInterval(pollProgressInterval);
                        }
                        pollProgressInterval = setInterval(function() {
                            const sessionId = window.lastGeotaggingSessionId;
                            if (!sessionId) return;
                            fetch(`/api/geotagging/progress/${sessionId}`)
                                .then(res => res.json())
                                .then(data => {
                                    if (typeof data.progress === 'number') {
                                        document.getElementById('progress-bar').style.width = data.progress + '%';
                                        document.getElementById('progress-bar').textContent = data.progress + '%';
                                        if (data.progress >= 100) {
                                            clearInterval(pollProgressInterval);
                                            pollProgressInterval = null;
                                        }
                                    }
                                });
                        }, 1000);

                        // Show success message
                        document.getElementById('success-message').textContent = response.message;
                        document.getElementById('results-card').classList.remove('d-none');
                        
                        // Set download link
                        const downloadButton = document.getElementById('download-button');
                        downloadButton.href = response.download_url;
                        
                        // Clean up session after download
                        downloadButton.addEventListener('click', function() {
                            const sessionId = response.download_url.split('/').pop();
                            
                            // Send cleanup request after a delay to allow download to start
                            setTimeout(function() {
                                fetch(`/api/geotagging/cleanup/${sessionId}`, {
                                    method: 'POST'
                                }).catch(error => {
                                    console.warn('Cleanup request failed:', error);
                                });
                            }, 5000);
                        });
                    } else {
                        let errorMessage = 'An error occurred while processing the images.';
                        let errorDetails = '';
                        
                        try {
                            const response = JSON.parse(xhr.responseText);
                            if (response.error) {
                                errorMessage = response.error;
                            }
                            if (response.details) {
                                errorDetails = response.details;
                            }
                        } catch (e) {
                            console.error('Error parsing response:', e);
                            errorDetails = xhr.responseText;
                        }
                        
                        console.error('Server response:', {
                            status: xhr.status,
                            statusText: xhr.statusText,
                            response: xhr.responseText
                        });
                        
                        // Handle specific HTTP status codes
                        switch (xhr.status) {
                            case 413:
                                errorMessage = 'The uploaded files are too large. Please reduce the file size or upload fewer files.';
                                break;
                            case 415:
                                errorMessage = 'One or more files are in an unsupported format. Please check your file types.';
                                break;
                            case 500:
                                errorMessage = 'A server error occurred. Please try again later.';
                                break;
                            case 503:
                                errorMessage = 'The server is temporarily unavailable. Please try again later.';
                                break;
                            case 504:
                                errorMessage = 'The request timed out. Please try again with fewer files or smaller file sizes.';
                                break;
                        }
                        
                        showAlert('Error', `${errorMessage}${errorDetails ? '\n\nDetails: ' + errorDetails : ''}`);
                    }
                    
                    // Hide progress
                    progressContainer.classList.add('d-none');

                    // Stop polling when request is done (in case of error)
                    if (pollProgressInterval && xhr.status !== 200) {
                        clearInterval(pollProgressInterval);
                        pollProgressInterval = null;
                    }
                }
            };
            
            xhr.onerror = function(e) {
                console.error('Network error details:', e);
                let errorMessage = 'A network error occurred. ';
                
                // Check if we're online
                if (!navigator.onLine) {
                    errorMessage += 'You appear to be offline. Please check your internet connection.';
                } else {
                    errorMessage += 'Please check your connection and try again. If the problem persists, the server may be temporarily unavailable.';
                }
                
                showAlert('Error', errorMessage);
                progressContainer.classList.add('d-none');
            };
            
            xhr.upload.onerror = function(e) {
                console.error('Upload error details:', e);
                let errorMessage = 'An error occurred while uploading the files. ';
                
                // Check if we're online
                if (!navigator.onLine) {
                    errorMessage += 'You appear to be offline. Please check your internet connection.';
                } else {
                    errorMessage += 'This could be due to a network issue or the server being temporarily unavailable. Please try again.';
                }
                
                showAlert('Error', errorMessage);
                progressContainer.classList.add('d-none');
            };

            // Add timeout handling
            xhr.timeout = 300000; // 5 minutes timeout
            xhr.ontimeout = function() {
                console.error('Request timed out');
                showAlert('Error', 'The request timed out. This could be due to large file sizes or a slow connection. Please try again with fewer files or smaller file sizes.');
                progressContainer.classList.add('d-none');
            };

            xhr.send(formData);
        } catch (error) {
            console.error('Error during form submission:', error);
            showAlert('Error', `An unexpected client-side error occurred: ${error.message}`);
            progressContainer.classList.add('d-none');
        }
    });
    
    // Handle clear button
    clearButton.addEventListener('click', function() {
        form.reset();
        document.getElementById('file-list').innerHTML = '';
        document.getElementById('file-list-container').classList.add('d-none');
        document.getElementById('results-card').classList.add('d-none');
        document.getElementById('progress-container').classList.add('d-none');
        document.getElementById('latitude').dataset.useRandom = 'false'; // Reset random coordinates flag
        selectedGeotaggingFiles = []; // Clear selected files
        
        // Set default datetime to now
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        
        datetimeInput.value = `${year}-${month}-${day}T${hours}:${minutes}`;

        // Re-initialize state and city dropdowns when clearing form
        const countrySelect = document.getElementById('cityPresetCountrySelect');
        const stateProvinceSelect = document.getElementById('cityPresetStateProvinceSelect');
        const cityPresetSelect = document.getElementById('city-preset');

        stateProvinceSelect.innerHTML = '<option value="">Select State/Province</option>';
        cityPresetSelect.innerHTML = '<option value="">Select a city preset</option>';
        stateProvinceSelect.disabled = true;
        cityPresetSelect.disabled = true;
        // Country select is re-populated by loadCityPresets on page load, no need to clear it.
    });
}

// Initialize conversion form
function initializeConversionForm() {
    const form = document.getElementById('conversion-form');
    const clearButton = document.getElementById('conversion-clear-button');
    
    // Handle form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Get selected files
        const fileInput = document.getElementById('conversion-file-input');
        if (fileInput.files.length === 0) {
            showAlert('Error', 'Please select at least one image file.');
            return;
        }
        
        // Prepare form data
        const formData = new FormData();
        
        // Add files
        for (let i = 0; i < fileInput.files.length; i++) {
            formData.append('files[]', fileInput.files[i]);
        }
        
        // Add output format
        formData.append('output_format', document.getElementById('conversion-output-format').value);
        
        // Show progress
        const progressContainer = document.getElementById('conversion-progress-container');
        const progressBar = document.getElementById('conversion-progress-bar');
        
        progressContainer.classList.remove('d-none');
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', 0);
        
        // Send request
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/conversion/process');
        
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = percentComplete + '%';
                progressBar.setAttribute('aria-valuenow', percentComplete);
            }
        });
        
        xhr.onload = function() {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                
                // Show success message
                document.getElementById('conversion-success-message').textContent = response.message;
                document.getElementById('conversion-results-card').classList.remove('d-none');
                
                // Set download link
                const downloadButton = document.getElementById('conversion-download-button');
                downloadButton.href = response.download_url;
                
                // Clean up session after download
                downloadButton.addEventListener('click', function() {
                    const sessionId = response.download_url.split('/').pop();
                    
                    // Send cleanup request after a delay to allow download to start
                    setTimeout(function() {
                        fetch(`/api/conversion/cleanup/${sessionId}`, {
                            method: 'POST'
                        });
                    }, 5000);
                });
            } else {
                let errorMessage = 'An error occurred while processing the images.';
                
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.error) {
                        errorMessage = response.error;
                    }
                } catch (e) {
                    console.error('Error parsing response:', e);
                }
                
                showAlert('Error', errorMessage);
            }
            
            // Hide progress
            progressContainer.classList.add('d-none');
        };
        
        xhr.onerror = function() {
            showAlert('Error', 'A network error occurred. Please try again.');
            progressContainer.classList.add('d-none');
        };
        
        xhr.send(formData);
    });
    
    // Handle clear button
    clearButton.addEventListener('click', function() {
        form.reset();
        document.getElementById('conversion-file-list').innerHTML = '';
        document.getElementById('conversion-file-list-container').classList.add('d-none');
        document.getElementById('conversion-results-card').classList.add('d-none');
        document.getElementById('conversion-progress-container').classList.add('d-none');
    });
}

// Initialize resizing form
function initializeResizingForm() {
    const form = document.getElementById('resizing-form');
    const clearButton = document.getElementById('resizing-clear-button');
    const resizeMode = document.getElementById('resize-mode');
    const dimensionsContainer = document.getElementById('dimensions-container');
    const percentageContainer = document.getElementById('percentage-container');
    const percentageInput = document.getElementById('percentage');
    const percentageValue = document.getElementById('percentage-value');
    
    // Handle resize mode change
    resizeMode.addEventListener('change', function() {
        if (this.value === 'percentage') {
            dimensionsContainer.classList.add('d-none');
            percentageContainer.classList.remove('d-none');
        } else {
            dimensionsContainer.classList.remove('d-none');
            percentageContainer.classList.add('d-none');
        }
    });
    
    // Handle percentage input change
    percentageInput.addEventListener('input', function() {
        percentageValue.textContent = this.value + '%';
    });
    
    // Handle form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Get selected files
        const fileInput = document.getElementById('resizing-file-input');
        if (fileInput.files.length === 0) {
            showAlert('Error', 'Please select at least one image file.');
            return;
        }
        
        // Prepare form data
        const formData = new FormData();
        
        // Add files
        for (let i = 0; i < fileInput.files.length; i++) {
            formData.append('files[]', fileInput.files[i]);
        }
        
        // Add resize parameters
        formData.append('resize_mode', resizeMode.value);
        
        if (resizeMode.value === 'percentage') {
            formData.append('percentage', percentageInput.value);
        } else {
            const width = document.getElementById('width').value;
            const height = document.getElementById('height').value;
            
            if (width) formData.append('width', width);
            if (height) formData.append('height', height);
        }
        
        // Add output format
        formData.append('output_format', document.getElementById('resizing-output-format').value);
        
        // Show progress
        const progressContainer = document.getElementById('resizing-progress-container');
        const progressBar = document.getElementById('resizing-progress-bar');
        
        progressContainer.classList.remove('d-none');
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', 0);
        
        // Send request
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/resizing/process');
        
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = percentComplete + '%';
                progressBar.setAttribute('aria-valuenow', percentComplete);
            }
        });
        
        xhr.onload = function() {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                
                // Show success message
                document.getElementById('resizing-success-message').textContent = response.message;
                document.getElementById('resizing-results-card').classList.remove('d-none');
                
                // Set download link
                const downloadButton = document.getElementById('resizing-download-button');
                downloadButton.href = response.download_url;
                
                // Clean up session after download
                downloadButton.addEventListener('click', function() {
                    const sessionId = response.download_url.split('/').pop();
                    
                    // Send cleanup request after a delay to allow download to start
                    setTimeout(function() {
                        fetch(`/api/resizing/cleanup/${sessionId}`, {
                            method: 'POST'
                        });
                    }, 5000);
                });
            } else {
                let errorMessage = 'An error occurred while processing the images.';
                
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.error) {
                        errorMessage = response.error;
                    }
                } catch (e) {
                    console.error('Error parsing response:', e);
                }
                
                showAlert('Error', errorMessage);
            }
            
            // Hide progress
            progressContainer.classList.add('d-none');
        };
        
        xhr.onerror = function() {
            showAlert('Error', 'A network error occurred. Please try again.');
            progressContainer.classList.add('d-none');
        };
        
        xhr.send(formData);
    });
    
    // Handle clear button
    clearButton.addEventListener('click', function() {
        form.reset();
        document.getElementById('resizing-file-list').innerHTML = '';
        document.getElementById('resizing-file-list-container').classList.add('d-none');
        document.getElementById('resizing-results-card').classList.add('d-none');
        document.getElementById('resizing-progress-container').classList.add('d-none');
        
        // Reset resize mode
        dimensionsContainer.classList.remove('d-none');
        percentageContainer.classList.add('d-none');
        
        // Reset percentage value
        percentageValue.textContent = '100%';
    });
}

// Initialize watermark form
function initializeWatermarkForm() {
    const form = document.getElementById('watermark-form');
    const clearButton = document.getElementById('watermark-clear-button');
    const watermarkType = document.getElementById('watermark-type');
    const watermarkTextContainer = document.getElementById('watermark-text-container');
    const watermarkImageContainer = document.getElementById('watermark-image-container');
    const opacityInput = document.getElementById('watermark-opacity');
    const opacityValue = document.getElementById('opacity-value');
    const sizeInput = document.getElementById('watermark-size');
    const sizeValue = document.getElementById('size-value');
    
    // Handle watermark type change
    watermarkType.addEventListener('change', function() {
        if (this.value === 'text') {
            watermarkTextContainer.classList.remove('d-none');
            watermarkImageContainer.classList.add('d-none');
        } else {
            watermarkTextContainer.classList.add('d-none');
            watermarkImageContainer.classList.remove('d-none');
        }
    });
    
    // Handle opacity input change
    opacityInput.addEventListener('input', function() {
        opacityValue.textContent = this.value + '%';
    });
    
    // Handle size input change
    sizeInput.addEventListener('input', function() {
        sizeValue.textContent = this.value + '%';
    });
    
    // Handle form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Get selected files
        const fileInput = document.getElementById('watermark-file-input');
        if (fileInput.files.length === 0) {
            showAlert('Error', 'Please select at least one image file.');
            return;
        }
        
        // Prepare form data
        const formData = new FormData();
        
        // Add files
        for (let i = 0; i < fileInput.files.length; i++) {
            formData.append('files[]', fileInput.files[i]);
        }
        
        // Add watermark parameters
        formData.append('watermark_type', watermarkType.value);
        
        if (watermarkType.value === 'text') {
            const watermarkText = document.getElementById('watermark-text').value;
            if (!watermarkText) {
                showAlert('Error', 'Please enter watermark text.');
                return;
            }
            formData.append('watermark_text', watermarkText);
        } else {
            const watermarkImage = document.getElementById('watermark-image').files[0];
            if (!watermarkImage) {
                showAlert('Error', 'Please select a watermark image.');
                return;
            }
            formData.append('watermark_image', watermarkImage);
        }
        
        formData.append('position', document.getElementById('watermark-position').value);
        formData.append('opacity', opacityInput.value);
        formData.append('size', sizeInput.value);
        
        // Add output format
        formData.append('output_format', document.getElementById('watermark-output-format').value);
        
        // Show progress
        const progressContainer = document.getElementById('watermark-progress-container');
        const progressBar = document.getElementById('watermark-progress-bar');
        
        progressContainer.classList.remove('d-none');
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', 0);
        
        // Send request
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/watermark/process');
        
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = percentComplete + '%';
                progressBar.setAttribute('aria-valuenow', percentComplete);
            }
        });
        
        xhr.onload = function() {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                
                // Show success message
                document.getElementById('watermark-success-message').textContent = response.message;
                document.getElementById('watermark-results-card').classList.remove('d-none');
                
                // Set download link
                const downloadButton = document.getElementById('watermark-download-button');
                downloadButton.href = response.download_url;
                
                // Clean up session after download
                downloadButton.addEventListener('click', function() {
                    const sessionId = response.download_url.split('/').pop();
                    
                    // Send cleanup request after a delay to allow download to start
                    setTimeout(function() {
                        fetch(`/api/watermark/cleanup/${sessionId}`, {
                            method: 'POST'
                        });
                    }, 5000);
                });
            } else {
                let errorMessage = 'An error occurred while processing the images.';
                
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.error) {
                        errorMessage = response.error;
                    }
                } catch (e) {
                    console.error('Error parsing response:', e);
                }
                
                showAlert('Error', errorMessage);
            }
            
            // Hide progress
            progressContainer.classList.add('d-none');
        };
        
        xhr.onerror = function() {
            showAlert('Error', 'A network error occurred. Please try again.');
            progressContainer.classList.add('d-none');
        };
        
        xhr.send(formData);
    });
    
    // Handle clear button
    clearButton.addEventListener('click', function() {
        form.reset();
        document.getElementById('watermark-file-list').innerHTML = '';
        document.getElementById('watermark-file-list-container').classList.add('d-none');
        document.getElementById('watermark-results-card').classList.add('d-none');
        document.getElementById('watermark-progress-container').classList.add('d-none');
        
        // Reset watermark type
        watermarkTextContainer.classList.remove('d-none');
        watermarkImageContainer.classList.add('d-none');
        
        // Reset opacity and size values
        opacityValue.textContent = '50%';
        sizeValue.textContent = '30%';
    });
}

// Initialize preset managers
function initializePresetManagers() {
    // City preset manager
    initializeCityPresetManager();
    
    // Client preset manager
    initializeClientPresetManager();
}

// Initialize city preset manager
function initializeCityPresetManager() {
    const addButton = document.getElementById('add-city-preset');
    const saveButton = document.getElementById('save-city-preset');
    const modal = new bootstrap.Modal(document.getElementById('city-preset-modal'));
    const form = document.getElementById('city-preset-form');
    
    // Handle add button click
    addButton.addEventListener('click', function() {
        // Reset form
        form.reset();
        document.getElementById('city-preset-id').value = '';
        document.getElementById('city-preset-modal-title').textContent = 'Add City Preset';
        
        // Show modal
        modal.show();
    });
    
    // Handle save button click
    saveButton.addEventListener('click', function() {
        // Validate form
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        
        // Get form values
        const id = document.getElementById('city-preset-id').value || generateId(document.getElementById('city-preset-name').value);
        const name = document.getElementById('city-preset-name').value;
        const country = document.getElementById('city-preset-country').value;
        const centerLat = parseFloat(document.getElementById('city-preset-center-lat').value);
        const centerLng = parseFloat(document.getElementById('city-preset-center-lng').value);
        const topLeftLat = parseFloat(document.getElementById('city-preset-top-left-lat').value);
        const topLeftLng = parseFloat(document.getElementById('city-preset-top-left-lng').value);
        const topRightLat = parseFloat(document.getElementById('city-preset-top-right-lat').value);
        const topRightLng = parseFloat(document.getElementById('city-preset-top-right-lng').value);
        const bottomLeftLat = parseFloat(document.getElementById('city-preset-bottom-left-lat').value);
        const bottomLeftLng = parseFloat(document.getElementById('city-preset-bottom-left-lng').value);
        const bottomRightLat = parseFloat(document.getElementById('city-preset-bottom-right-lat').value);
        const bottomRightLng = parseFloat(document.getElementById('city-preset-bottom-right-lng').value);
        const zoomLevel = parseInt(document.getElementById('city-preset-zoom-level').value);
        
        // Create preset object
        const preset = {
            id,
            name,
            country,
            center: {
                lat: centerLat,
                lng: centerLng
            },
            boundaries: {
                top_left: {
                    lat: topLeftLat,
                    lng: topLeftLng
                },
                top_right: {
                    lat: topRightLat,
                    lng: topRightLng
                },
                bottom_left: {
                    lat: bottomLeftLat,
                    lng: bottomLeftLng
                },
                bottom_right: {
                    lat: bottomRightLat,
                    lng: bottomRightLng
                }
            },
            zoom_level: zoomLevel
        };
        
        // Check if preset already exists
        const existingIndex = cityPresets.presets.findIndex(p => p.id === id);
        
        if (existingIndex !== -1) {
            // Update existing preset
            cityPresets.presets[existingIndex] = preset;
        } else {
            // Add new preset
            cityPresets.presets.push(preset);
        }
        
        // Save presets
        saveCityPresets();
        
        // Hide modal
        modal.hide();
    });
}

// Initialize client preset manager
function initializeClientPresetManager() {
    const addButton = document.getElementById('add-client-preset');
    const saveButton = document.getElementById('save-client-preset');
    const modal = new bootstrap.Modal(document.getElementById('client-preset-modal'));
    const form = document.getElementById('client-preset-form');
    
    // Handle add button click
    addButton.addEventListener('click', function() {
        // Reset form
        form.reset();
        document.getElementById('client-preset-id').value = '';
        document.getElementById('client-preset-modal-title').textContent = 'Add Client Preset';
        
        // Show modal
        modal.show();
    });
    
    // Handle save button click
    saveButton.addEventListener('click', function() {
        // Validate form
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        
        // Get form values
        const id = document.getElementById('client-preset-id').value || generateId(document.getElementById('client-preset-name').value);
        const name = document.getElementById('client-preset-name').value;
        const creator = document.getElementById('client-preset-creator').value;
        const creatorTitle = document.getElementById('client-preset-creator-title').value;
        const address = document.getElementById('client-preset-address').value;
        const city = document.getElementById('client-preset-city').value;
        const state = document.getElementById('client-preset-state').value;
        const postalCode = document.getElementById('client-preset-postal-code').value;
        const country = document.getElementById('client-preset-country').value;
        const phone = document.getElementById('client-preset-phone').value;
        const email = document.getElementById('client-preset-email').value;
        const url = document.getElementById('client-preset-url').value;
        const keywords = document.getElementById('client-preset-keywords').value;
        
        // Create preset object
        const preset = {
            id,
            name
        };
        
        if (creator) preset.creator = creator;
        if (creatorTitle) preset.creatorTitle = creatorTitle;
        if (address) preset.address = address;
        if (city) preset.city = city;
        if (state) preset.state = state;
        if (postalCode) preset.postalCode = postalCode;
        if (country) preset.country = country;
        if (phone) preset.phone = phone;
        if (email) preset.email = email;
        if (url) preset.url = url;
        if (keywords) preset.keywords = keywords.split(',').map(k => k.trim()).filter(k => k);
        
        // Check if preset already exists
        const existingIndex = clientPresets.presets.findIndex(p => p.id === id);
        
        if (existingIndex !== -1) {
            // Update existing preset
            clientPresets.presets[existingIndex] = preset;
        } else {
            // Add new preset
            clientPresets.presets.push(preset);
        }
        
        // Save presets
        saveClientPresets();
        
        // Hide modal
        modal.hide();
    });
}

// Generate ID from name
function generateId(name) {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, '_');
}

// Load city presets (for geotagging form and presets manager)
async function loadCityPresets() {
    try {
        const response = await fetch('/api/presets/city');
        const data = await response.json();
        cityPresetsData = data.countries; // Store the hierarchical data

        // Populate country select in geotagging form
        const countrySelect = document.getElementById('cityPresetCountrySelect');
        countrySelect.innerHTML = '<option value="">Select Country</option>';
        // Sort countries alphabetically
        Object.keys(cityPresetsData).sort().forEach(country => {
            const option = document.createElement('option');
            option.value = country;
            option.textContent = country;
            countrySelect.appendChild(option);
        });

        // Update city presets table (for presets manager page)
        updateCityPresetsTable();

        // Reset state and city dropdowns for the geotagging form
        loadStatesForCityPresets('');
        loadCitiesForCityPresets('', '');

    } catch (error) {
        console.error('Error loading city presets:', error);
    }
}

// Load client presets
function loadClientPresets() {
    fetch('/api/presets/client')
        .then(response => response.json())
        .then(data => {
            clientPresets = data;
            updateClientPresetSelects();
            updateClientPresetsTable();
            // Add event listener after presets are loaded
            document.getElementById('client-preset').addEventListener('change', function() {
                if (this.value) {
                    const preset = clientPresets.presets.find(p => p.id === this.value);
                    if (preset) {
                        // Fill contact information
                        if (preset.contact_info) {
                            if (preset.contact_info.byline) document.getElementById('creator').value = preset.contact_info.byline;
                            if (preset.contact_info.byline_title) document.getElementById('creator-title').value = preset.contact_info.byline_title;
                            if (preset.contact_info.address) document.getElementById('address').value = preset.contact_info.address;
                            if (preset.contact_info.city) document.getElementById('city').value = preset.contact_info.city;
                            if (preset.contact_info.state_province) document.getElementById('state').value = preset.contact_info.state_province;
                            if (preset.contact_info.postal_code) document.getElementById('postal-code').value = preset.contact_info.postal_code;
                            if (preset.contact_info.country) document.getElementById('country').value = preset.contact_info.country;
                            if (preset.contact_info.phone) document.getElementById('phone').value = preset.contact_info.phone;
                            if (preset.contact_info.email) document.getElementById('email').value = preset.contact_info.email;
                            if (preset.contact_info.url) document.getElementById('url').value = preset.contact_info.url;
                        }
                        // Keywords are directly on the preset object
                        if (preset.keywords) document.getElementById('keywords').value = preset.keywords.join(', ');
                    }
                }
            });
        })
        .catch(error => {
            console.error('Error loading client presets:', error);
        });
}

// Save city presets
function saveCityPresets() {
    fetch('/api/presets/city', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ version: '2.0', countries: cityPresetsData }) // Send the full hierarchical object
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // After saving, re-populate all dropdowns and tables
                loadCityPresets(); // This will refresh the geotagging page dropdowns too
                updateCityPresetsTable();
            } else {
                showAlert('Error', data.error || 'Failed to save city presets.');
            }
        })
        .catch(error => {
            console.error('Error saving city presets:', error);
            showAlert('Error', 'A network error occurred while saving city presets.');
        });
}

// Save client presets
function saveClientPresets() {
    fetch('/api/presets/client', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(clientPresets)
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                updateClientPresetSelects();
                updateClientPresetsTable();
            } else {
                showAlert('Error', data.error || 'Failed to save client presets.');
            }
        })
        .catch(error => {
            console.error('Error saving client presets:', error);
            showAlert('Error', 'A network error occurred while saving client presets.');
        });
}

// This function is no longer needed in its current form for geotagging select. 
// Its logic is now part of loadCitiesForCityPresets.
// Keeping it as a placeholder for potential future use or to avoid errors if referenced elsewhere unexpectedly.
function updateCityPresetSelects() {
    // This function's role is now handled by loadStatesForCityPresets and loadCitiesForCityPresets
    // when populating the geotagging form's city preset dropdown (select#city-preset).
    // It is still called by loadCityPresets, but its internal logic is effectively a no-op for select#city-preset.
    // It is primarily used by the presets manager to update the city preset list for editing. 
    
    // If there are other select#city-preset elements that need to display all cities (e.g. for selection outside cascading dropdowns),
    // this function would need to be adapted or duplicated.
}

// Helper function to find a city preset by ID in the hierarchical data
function findCityPreset(id) {
    for (const country in cityPresetsData) {
        for (const stateProvince in cityPresetsData[country]) {
            const city = cityPresetsData[country][stateProvince].find(c => c.id === id);
            if (city) return city;
        }
    }
    return null;
}

// Update client preset selects
function updateClientPresetSelects() {
    const selects = document.querySelectorAll('select#client-preset');
    
    selects.forEach(select => {
        // Save current value
        const currentValue = select.value;
        
        // Clear options
        select.innerHTML = '<option value="">Select a client preset</option>';
        
        // Add options
        clientPresets.presets.forEach(preset => {
            const option = document.createElement('option');
            option.value = preset.id;
            option.textContent = preset.name;
            select.appendChild(option);
        });
        
        // Restore value if it still exists
        if (currentValue && clientPresets.presets.some(p => p.id === currentValue)) {
            select.value = currentValue;
        }
    });
}

// Update city presets table
function updateCityPresetsTable() {
    const table = document.getElementById('city-presets-table');
    const tbody = table.querySelector('tbody');
    
    // Clear table
    tbody.innerHTML = '';
    
    // Create array of all entries for sorting
    const allEntries = [];
    for (const countryName in cityPresetsData) {
        for (const stateProvinceName in cityPresetsData[countryName]) {
            cityPresetsData[countryName][stateProvinceName].forEach(preset => {
                allEntries.push({
                    preset,
                    countryName,
                    stateProvinceName
                });
            });
        }
    }

    // Sort entries by country, state/province, and city name
    allEntries.sort((a, b) => {
        // First sort by country
        const countryCompare = a.countryName.localeCompare(b.countryName);
        if (countryCompare !== 0) return countryCompare;
        
        // Then by state/province
        const stateCompare = a.stateProvinceName.localeCompare(b.stateProvinceName);
        if (stateCompare !== 0) return stateCompare;
        
        // Finally by city name
        return a.preset.name.localeCompare(b.preset.name);
    });

    // Add sorted rows to table
    allEntries.forEach(({ preset, countryName, stateProvinceName }) => {
        const tr = document.createElement('tr');
        
        // Name
        const tdName = document.createElement('td');
        tdName.textContent = preset.name;
        tr.appendChild(tdName);
        
        // Country
        const tdCountry = document.createElement('td');
        tdCountry.textContent = countryName;
        tr.appendChild(tdCountry);
        
        // State/Province
        const tdStateProvince = document.createElement('td');
        tdStateProvince.textContent = stateProvinceName;
        tr.appendChild(tdStateProvince);
        
        // Center coordinates
        const tdCoordinates = document.createElement('td');
        tdCoordinates.textContent = `${preset.center.lat.toFixed(6)}, ${preset.center.lng.toFixed(6)}`;
        tr.appendChild(tdCoordinates);
        
        // Actions
        const tdActions = document.createElement('td');
        
        // Edit button
        const editButton = document.createElement('button');
        editButton.className = 'btn btn-sm btn-primary me-2';
        editButton.innerHTML = '<i class="bi bi-pencil"></i>';
        editButton.addEventListener('click', function() {
            editCityPreset(preset, stateProvinceName, countryName);
        });
        tdActions.appendChild(editButton);
        
        // Delete button
        const deleteButton = document.createElement('button');
        deleteButton.className = 'btn btn-sm btn-danger';
        deleteButton.innerHTML = '<i class="bi bi-trash"></i>';
        deleteButton.addEventListener('click', function() {
            deleteCityPreset(preset.id, stateProvinceName, countryName);
        });
        tdActions.appendChild(deleteButton);
        
        tr.appendChild(tdActions);
        
        tbody.appendChild(tr);
    });
}

// Update client presets table
function updateClientPresetsTable() {
    const table = document.getElementById('client-presets-table');
    const tbody = table.querySelector('tbody');
    
    // Clear table
    tbody.innerHTML = '';
    
    // Sort client presets alphabetically by name
    const sortedPresets = [...clientPresets.presets].sort((a, b) => 
        a.name.localeCompare(b.name)
    );
    
    // Add sorted rows
    sortedPresets.forEach(preset => {
        const tr = document.createElement('tr');
        
        // Name
        const tdName = document.createElement('td');
        tdName.textContent = preset.name;
        tr.appendChild(tdName);
        
        // Contact
        const tdContact = document.createElement('td');
        const contactInfo = [];
        if (preset.creator) contactInfo.push(preset.creator);
        if (preset.phone) contactInfo.push(preset.phone);
        if (preset.email) contactInfo.push(preset.email);
        tdContact.textContent = contactInfo.join(' | ');
        tr.appendChild(tdContact);
        
        // Location
        const tdLocation = document.createElement('td');
        const locationInfo = [];
        if (preset.city) locationInfo.push(preset.city);
        if (preset.state) locationInfo.push(preset.state);
        if (preset.country) locationInfo.push(preset.country);
        tdLocation.textContent = locationInfo.join(', ');
        tr.appendChild(tdLocation);
        
        // Actions
        const tdActions = document.createElement('td');
        
        // Edit button
        const editButton = document.createElement('button');
        editButton.className = 'btn btn-sm btn-primary me-2';
        editButton.innerHTML = '<i class="bi bi-pencil"></i>';
        editButton.addEventListener('click', function() {
            editClientPreset(preset);
        });
        tdActions.appendChild(editButton);
        
        // Delete button
        const deleteButton = document.createElement('button');
        deleteButton.className = 'btn btn-sm btn-danger';
        deleteButton.innerHTML = '<i class="bi bi-trash"></i>';
        deleteButton.addEventListener('click', function() {
            deleteClientPreset(preset.id);
        });
        tdActions.appendChild(deleteButton);
        
        tr.appendChild(tdActions);
        
        tbody.appendChild(tr);
    });
}

// Edit city preset
function editCityPreset(preset, stateProvinceName, countryName) {
    // Set form values
    document.getElementById('city-preset-id').value = preset.id;
    document.getElementById('city-preset-name').value = preset.name;
    document.getElementById('city-preset-country').value = countryName;
    document.getElementById('city-preset-state-province').value = stateProvinceName;
    document.getElementById('city-preset-center-lat').value = preset.center.lat;
    document.getElementById('city-preset-center-lng').value = preset.center.lng;
    document.getElementById('city-preset-top-left-lat').value = preset.boundaries.top_left.lat;
    document.getElementById('city-preset-top-left-lng').value = preset.boundaries.top_left.lng;
    document.getElementById('city-preset-top-right-lat').value = preset.boundaries.top_right.lat;
    document.getElementById('city-preset-top-right-lng').value = preset.boundaries.top_right.lng;
    document.getElementById('city-preset-bottom-left-lat').value = preset.boundaries.bottom_left.lat;
    document.getElementById('city-preset-bottom-left-lng').value = preset.boundaries.bottom_left.lng;
    document.getElementById('city-preset-bottom-right-lat').value = preset.boundaries.bottom_right.lat;
    document.getElementById('city-preset-bottom-right-lng').value = preset.boundaries.bottom_right.lng;
    document.getElementById('city-preset-zoom-level').value = preset.zoom_level;
    
    // Set modal title
    document.getElementById('city-preset-modal-title').textContent = 'Edit City Preset';
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('city-preset-modal'));
    modal.show();
}

// Delete city preset
function deleteCityPreset(id, stateProvinceName, countryName) {
    if (confirm('Are you sure you want to delete this city preset?')) {
        // Find and remove the preset from the hierarchical data
        if (cityPresetsData[countryName] && cityPresetsData[countryName][stateProvinceName]) {
            cityPresetsData[countryName][stateProvinceName] = cityPresetsData[countryName][stateProvinceName].filter(p => p.id !== id);
            
            // Clean up empty state/province arrays
            if (cityPresetsData[countryName][stateProvinceName].length === 0) {
                delete cityPresetsData[countryName][stateProvinceName];
            }
            
            // Clean up empty country objects
            if (Object.keys(cityPresetsData[countryName]).length === 0) {
                delete cityPresetsData[countryName];
            }
        }
        
        // Save presets
        saveCityPresets();
    }
}

// Edit client preset
function editClientPreset(preset) {
    // Set form values
    document.getElementById('client-preset-id').value = preset.id;
    document.getElementById('client-preset-name').value = preset.name;
    document.getElementById('client-preset-creator').value = preset.creator || '';
    document.getElementById('client-preset-creator-title').value = preset.creatorTitle || '';
    document.getElementById('client-preset-address').value = preset.address || '';
    document.getElementById('client-preset-city').value = preset.city || '';
    document.getElementById('client-preset-state').value = preset.state || '';
    document.getElementById('client-preset-postal-code').value = preset.postalCode || '';
    document.getElementById('client-preset-country').value = preset.country || '';
    document.getElementById('client-preset-phone').value = preset.phone || '';
    document.getElementById('client-preset-email').value = preset.email || '';
    document.getElementById('client-preset-url').value = preset.url || '';
    document.getElementById('client-preset-keywords').value = preset.keywords ? preset.keywords.join(', ') : '';
    
    // Set modal title
    document.getElementById('client-preset-modal-title').textContent = 'Edit Client Preset';
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('client-preset-modal'));
    modal.show();
}

// Delete client preset
function deleteClientPreset(id) {
    if (confirm('Are you sure you want to delete this client preset?')) {
        // Remove preset
        clientPresets.presets = clientPresets.presets.filter(p => p.id !== id);
        
        // Save presets
        saveClientPresets();
    }
}

// Show alert
function showAlert(title, message) {
    document.getElementById('alert-modal-title').textContent = title;
    document.getElementById('alert-modal-message').textContent = message;
    
    const modal = new bootstrap.Modal(document.getElementById('alert-modal'));
    modal.show();
}

// Function to load states/provinces for a given country
function loadStatesForCityPresets(country) {
    const stateProvinceSelect = document.getElementById('cityPresetStateProvinceSelect');
    const cityPresetSelect = document.getElementById('city-preset');

    stateProvinceSelect.innerHTML = '<option value="">Select State/Province</option>';
    cityPresetSelect.innerHTML = '<option value="">Select a city preset</option>';
    stateProvinceSelect.disabled = true;
    cityPresetSelect.disabled = true;

    if (country && cityPresetsData[country]) {
        // Sort states/provinces alphabetically
        Object.keys(cityPresetsData[country]).sort().forEach(state => {
            const option = document.createElement('option');
            option.value = state;
            option.textContent = state;
            stateProvinceSelect.appendChild(option);
        });
        stateProvinceSelect.disabled = false;
    }
}

// Function to load cities for a given country and state/province
function loadCitiesForCityPresets(country, stateProvince) {
    const cityPresetSelect = document.getElementById('city-preset');

    cityPresetSelect.innerHTML = '<option value="">Select a city preset</option>';
    cityPresetSelect.disabled = true;

    if (country && stateProvince && cityPresetsData[country] && cityPresetsData[country][stateProvince]) {
        // Sort cities alphabetically
        [...cityPresetsData[country][stateProvince]]
            .sort((a, b) => a.name.localeCompare(b.name))
            .forEach(city => {
                const option = document.createElement('option');
                option.value = city.id;
                option.textContent = city.name;
                cityPresetSelect.appendChild(option);
            });
        cityPresetSelect.disabled = false;
    }
}
