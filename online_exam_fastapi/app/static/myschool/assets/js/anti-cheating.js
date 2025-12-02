/**
 * Anti-Cheating Measures for Online Exams
 * Implements 6 security features following INVEST principles
 */

(function() {
  'use strict';

  // Configuration
  const config = {
    showWarnings: true,
    enableFullscreen: true,
    trackTabSwitches: true,
    logToServer: true
  };

  // Exam context data (must be set from template)
  let examContext = {
    examId: null,
    studentId: null,
    attemptId: null,  // For essay attempts
    logEndpoint: null  // Will be set based on exam type
  };

  // Counter for tab switches
  let tabSwitchCount = 0;

  // Initialize exam context from data attributes or global variables
  function initExamContext() {
    // Try to get from data attributes on body or a script tag
    const contextScript = document.getElementById('exam-context-data');
    if (contextScript) {
      try {
        const data = JSON.parse(contextScript.textContent);
        examContext.examId = data.exam_id;
        examContext.studentId = data.student_id;
        examContext.attemptId = data.attempt_id || null;
        examContext.logEndpoint = data.log_endpoint || null;
      } catch (e) {
        console.warn('Failed to parse exam context data:', e);
      }
    }
  }

  // Log activity to server
  function logActivity(activityType, metadata, severity = 'low') {
    if (!config.logToServer) return;
    if (!examContext.examId || !examContext.studentId) {
      console.warn('Cannot log activity: exam context not initialized');
      return;
    }

    // Determine endpoint based on attempt_id presence (essay vs MCQ)
    const endpoint = examContext.logEndpoint || 
                    (examContext.attemptId 
                      ? `/essay/${examContext.examId}/log-activity`
                      : `/exams/${examContext.examId}/log-activity`);

    const payload = {
      student_id: examContext.studentId,
      attempt_id: examContext.attemptId,
      activity_type: activityType,
      metadata: metadata,
      severity: severity
    };

    // Send async (fire and forget)
    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).catch(function(err) {
      console.warn('Failed to log activity to server:', err);
    });
  }

  // ============================================================================
  // USER STORY 1: Disable Right-Click Context Menu
  // ============================================================================
  function disableRightClick() {
    document.addEventListener('contextmenu', function(e) {
      e.preventDefault();
      logActivity('right_click_attempt', { 
        target: e.target.tagName,
        timestamp: new Date().toISOString()
      }, 'medium');
      if (config.showWarnings) {
        showWarning('Right-click is disabled during exams.');
      }
      return false;
    }, false);
  }

  // ============================================================================
  // USER STORY 2: Block Copy/Paste Keyboard Shortcuts
  // ============================================================================
  function blockCopyPasteShortcuts() {
    document.addEventListener('keydown', function(e) {
      // Check for Ctrl (Windows/Linux) or Cmd (Mac)
      const isModifierPressed = e.ctrlKey || e.metaKey;
      
      // Block Ctrl+C / Cmd+C (Copy)
      if (isModifierPressed && e.key === 'c' && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        logActivity('copy_attempt', {
          key: e.key,
          ctrlKey: e.ctrlKey,
          metaKey: e.metaKey,
          target: e.target.tagName,
          timestamp: new Date().toISOString()
        }, 'medium');
        if (config.showWarnings) {
          showWarning('Copying is disabled during exams.');
        }
        return false;
      }
      
      // Block Ctrl+V / Cmd+V (Paste)
      if (isModifierPressed && e.key === 'v' && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        logActivity('paste_attempt', {
          key: e.key,
          ctrlKey: e.ctrlKey,
          metaKey: e.metaKey,
          target: e.target.tagName,
          timestamp: new Date().toISOString()
        }, 'high');
        if (config.showWarnings) {
          showWarning('Pasting is disabled during exams.');
        }
        return false;
      }
      
      // Block Ctrl+X / Cmd+X (Cut)
      if (isModifierPressed && e.key === 'x' && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        logActivity('cut_attempt', {
          key: e.key,
          ctrlKey: e.ctrlKey,
          metaKey: e.metaKey,
          target: e.target.tagName,
          timestamp: new Date().toISOString()
        }, 'medium');
        if (config.showWarnings) {
          showWarning('Cutting is disabled during exams.');
        }
        return false;
      }
      
      // Block Ctrl+A / Cmd+A (Select All) - but allow within textareas/inputs for editing answers
      if (isModifierPressed && e.key === 'a' && !e.shiftKey && !e.altKey) {
        const target = e.target;
        // Allow Ctrl+A within textareas and inputs for answer editing
        if (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT') {
          return true;
        }
        e.preventDefault();
        if (config.showWarnings) {
          showWarning('Select All is disabled during exams.');
        }
        return false;
      }
    }, false);
  }

  // ============================================================================
  // USER STORY 3: Disable Text Selection
  // ============================================================================
  function disableTextSelection() {
    // CSS approach: disable text selection via styles
    const style = document.createElement('style');
    style.textContent = `
      body {
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
        user-select: none !important;
      }
      /* Allow selection in textareas and inputs (students need to type answers) */
      textarea, input[type="text"], input[type="email"], input[type="password"], 
      input[type="radio"], input[type="checkbox"], .form-check, .form-check-label {
        -webkit-user-select: text !important;
        -moz-user-select: text !important;
        -ms-user-select: text !important;
        user-select: text !important;
      }
    `;
    document.head.appendChild(style);

    // JavaScript fallback: prevent selection via events
    document.addEventListener('selectstart', function(e) {
      // Allow selection in textareas and inputs (for typing answers)
      if (e.target.tagName === 'TEXTAREA' || 
          e.target.tagName === 'INPUT' ||
          e.target.isContentEditable) {
        return true;
      }
      // Allow selection within form-check labels (for radio buttons)
      if (e.target.closest('.form-check')) {
        return true;
      }
      e.preventDefault();
      return false;
    }, false);

    // Prevent drag (which can be used to select text)
    document.addEventListener('dragstart', function(e) {
      if (e.target.tagName !== 'TEXTAREA' && e.target.tagName !== 'INPUT') {
        e.preventDefault();
        return false;
      }
    }, false);
  }

  // ============================================================================
  // USER STORY 4: Block Developer Tools Keyboard Shortcuts
  // ============================================================================
  function blockDeveloperToolsShortcuts() {
    document.addEventListener('keydown', function(e) {
      // Block F12 (Open DevTools)
      if (e.key === 'F12') {
        e.preventDefault();
        logActivity('devtools_attempt', {
          shortcut: 'F12',
          timestamp: new Date().toISOString()
        }, 'high');
        if (config.showWarnings) {
          showWarning('Developer tools are disabled during exams.');
        }
        return false;
      }

      // Block Ctrl+Shift+I / Cmd+Opt+I (Open DevTools)
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'I') {
        e.preventDefault();
        logActivity('devtools_attempt', {
          shortcut: 'Ctrl+Shift+I / Cmd+Opt+I',
          timestamp: new Date().toISOString()
        }, 'high');
        if (config.showWarnings) {
          showWarning('Developer tools are disabled during exams.');
        }
        return false;
      }

      // Block Ctrl+Shift+J / Cmd+Opt+J (Open Console)
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'J') {
        e.preventDefault();
        logActivity('devtools_attempt', {
          shortcut: 'Ctrl+Shift+J / Cmd+Opt+J',
          timestamp: new Date().toISOString()
        }, 'high');
        if (config.showWarnings) {
          showWarning('Developer tools are disabled during exams.');
        }
        return false;
      }

      // Block Ctrl+Shift+C / Cmd+Opt+C (Inspect Element)
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'C') {
        e.preventDefault();
        logActivity('devtools_attempt', {
          shortcut: 'Ctrl+Shift+C / Cmd+Opt+C',
          timestamp: new Date().toISOString()
        }, 'high');
        if (config.showWarnings) {
          showWarning('Developer tools are disabled during exams.');
        }
        return false;
      }

      // Block Ctrl+U / Cmd+U (View Page Source)
      if ((e.ctrlKey || e.metaKey) && e.key === 'u' && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        logActivity('view_source_attempt', {
          shortcut: 'Ctrl+U / Cmd+U',
          timestamp: new Date().toISOString()
        }, 'medium');
        if (config.showWarnings) {
          showWarning('Viewing page source is disabled during exams.');
        }
        return false;
      }

      // Block Ctrl+Shift+Del / Cmd+Shift+Del (Clear browsing data - can interrupt exam)
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'Delete') {
        e.preventDefault();
        return false;
      }
    }, false);

    // Additional protection: disable right-click + inspect (already handled by right-click block)
    // Try to detect DevTools opening via console warnings (limited effectiveness)
    let devtools = { open: false, orientation: null };
    const threshold = 160;
    setInterval(function() {
      if (window.outerHeight - window.innerHeight > threshold || 
          window.outerWidth - window.innerWidth > threshold) {
        if (!devtools.open) {
          devtools.open = true;
          logActivity('devtools_detected', {
            method: 'window_size_detection',
            window_height_diff: window.outerHeight - window.innerHeight,
            window_width_diff: window.outerWidth - window.innerWidth,
            timestamp: new Date().toISOString()
          }, 'high');
          if (config.showWarnings) {
            showWarning('Please close developer tools. Your activity is being monitored.');
          }
        }
      } else {
        devtools.open = false;
      }
    }, 500);
  }

  // ============================================================================
  // USER STORY 5: Detect Tab/Window Switching
  // ============================================================================
  function detectTabSwitching() {
    if (!config.trackTabSwitches) return;

    // Create warning element
    let warningElement = null;
    function createWarningElement() {
      if (warningElement) return warningElement;
      warningElement = document.createElement('div');
      warningElement.id = 'tab-switch-warning';
      warningElement.className = 'alert alert-warning alert-dismissible fade show position-fixed';
      warningElement.style.cssText = 'top: 20px; right: 20px; z-index: 10000; max-width: 400px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);';
      warningElement.innerHTML = `
        <strong>Warning:</strong> You switched tabs/windows. Please stay on the exam page.
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
      `;
      document.body.appendChild(warningElement);
      return warningElement;
    }

    document.addEventListener('visibilitychange', function() {
      if (document.hidden) {
        // Tab/window became hidden
        tabSwitchCount++;
        
        // Log tab switch to server
        logActivity('tab_switch', {
          count: tabSwitchCount,
          timestamp: new Date().toISOString(),
          visibility_state: 'hidden'
        }, tabSwitchCount > 5 ? 'high' : tabSwitchCount > 2 ? 'medium' : 'low');
        
        if (config.showWarnings) {
          const warning = createWarningElement();
          warning.style.display = 'block';
          
          // Auto-hide after 5 seconds
          setTimeout(function() {
            if (warning && warning.parentNode) {
              warning.classList.remove('show');
              setTimeout(function() {
                if (warning && warning.parentNode) {
                  warning.style.display = 'none';
                }
              }, 150);
            }
          }, 5000);
        }
        
        console.log(`Tab switch detected. Count: ${tabSwitchCount}`);
      } else {
        // Tab/window became visible again
        if (config.showWarnings && warningElement) {
          warningElement.style.display = 'block';
          setTimeout(function() {
            if (warningElement && warningElement.parentNode) {
              warningElement.classList.remove('show');
              setTimeout(function() {
                if (warningElement && warningElement.parentNode) {
                  warningElement.style.display = 'none';
                }
              }, 150);
            }
          }, 3000);
        }
      }
    });

    // Also detect window blur/focus
    window.addEventListener('blur', function() {
      tabSwitchCount++;
      logActivity('window_blur', {
        count: tabSwitchCount,
        timestamp: new Date().toISOString()
      }, tabSwitchCount > 5 ? 'high' : tabSwitchCount > 2 ? 'medium' : 'low');
      if (config.showWarnings) {
        createWarningElement();
      }
    });
  }

  // ============================================================================
  // USER STORY 6: Encourage Fullscreen Mode
  // ============================================================================
  function encourageFullscreen() {
    if (!config.enableFullscreen) return;

    // Check if already in fullscreen
    function isFullscreen() {
      return !!(document.fullscreenElement || 
                document.webkitFullscreenElement || 
                document.mozFullScreenElement || 
                document.msFullscreenElement);
    }

    // Request fullscreen
    function requestFullscreen() {
      const element = document.documentElement;
      if (element.requestFullscreen) {
        element.requestFullscreen().catch(function(err) {
          console.log('Fullscreen request failed:', err);
        });
      } else if (element.webkitRequestFullscreen) {
        element.webkitRequestFullscreen();
      } else if (element.mozRequestFullScreen) {
        element.mozRequestFullScreen();
      } else if (element.msRequestFullscreen) {
        element.msRequestFullscreen();
      }
    }

    // Show fullscreen prompt on exam start
    function showFullscreenPrompt() {
      if (isFullscreen()) return;

      const prompt = document.createElement('div');
      prompt.id = 'fullscreen-prompt';
      prompt.className = 'alert alert-info alert-dismissible fade show position-fixed';
      prompt.style.cssText = 'top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 10001; max-width: 500px; text-align: center;';
      prompt.innerHTML = `
        <h5>Enter Fullscreen Mode</h5>
        <p>For the best exam experience, please enter fullscreen mode to focus on your exam.</p>
        <button type="button" class="btn btn-primary me-2" onclick="window.enableFullscreen(); this.closest('.alert').remove();">
          Enter Fullscreen
        </button>
        <button type="button" class="btn btn-secondary" data-bs-dismiss="alert" aria-label="Close">
          Continue Anyway
        </button>
      `;
      document.body.appendChild(prompt);

      // Auto-hide after 10 seconds if not clicked
      setTimeout(function() {
        if (prompt && prompt.parentNode) {
          prompt.classList.remove('show');
          setTimeout(function() {
            if (prompt && prompt.parentNode) {
              prompt.remove();
            }
          }, 150);
        }
      }, 10000);
    }

    // Expose fullscreen function globally for button click
    window.enableFullscreen = function() {
      requestFullscreen();
    };

    // Show prompt after a short delay (allows page to load)
    setTimeout(function() {
      if (!isFullscreen()) {
        showFullscreenPrompt();
      }
    }, 1000);

    // Monitor fullscreen changes
    document.addEventListener('fullscreenchange', function() {
      const currentlyFullscreen = isFullscreen();
      if (!currentlyFullscreen) {
        // User exited fullscreen - log this activity
        logActivity('fullscreen_exit', {
          timestamp: new Date().toISOString()
        }, 'low');
        // Optionally show prompt again (commented out to avoid annoyance)
        // if (document.getElementById('fullscreen-prompt') === null) {
        //   showFullscreenPrompt();
        // }
      } else {
        // User entered fullscreen - log positive action
        logActivity('fullscreen_enter', {
          timestamp: new Date().toISOString()
        }, 'low');
      }
    });
  }

  // ============================================================================
  // Helper Functions
  // ============================================================================
  function showWarning(message) {
    // Create a temporary warning toast
    const toast = document.createElement('div');
    toast.className = 'alert alert-warning alert-dismissible fade show position-fixed';
    toast.style.cssText = 'top: 80px; right: 20px; z-index: 10000; max-width: 350px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);';
    toast.innerHTML = `
      <strong>Warning:</strong> ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    document.body.appendChild(toast);

    // Auto-hide after 3 seconds
    setTimeout(function() {
      if (toast && toast.parentNode) {
        toast.classList.remove('show');
        setTimeout(function() {
          if (toast && toast.parentNode) {
            toast.remove();
          }
        }, 150);
      }
    }, 3000);
  }

  // ============================================================================
  // Initialize All Anti-Cheating Measures
  // ============================================================================
  function init() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
      return;
    }

    // Initialize exam context first
    initExamContext();

    // Initialize all features
    disableRightClick();
    blockCopyPasteShortcuts();
    disableTextSelection();
    blockDeveloperToolsShortcuts();
    detectTabSwitching();
    encourageFullscreen();

    // Log that anti-cheating measures were activated
    if (examContext.examId && examContext.studentId) {
      logActivity('anti_cheating_activated', {
        timestamp: new Date().toISOString(),
        user_agent: navigator.userAgent,
        screen_resolution: `${window.screen.width}x${window.screen.height}`
      }, 'low');
    }

    console.log('Anti-cheating measures activated');
  }

  // Start initialization
  init();

})();

