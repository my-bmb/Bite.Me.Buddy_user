import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getAuth, signInWithPhoneNumber, RecaptchaVerifier } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

const firebaseConfig = {
  apiKey: "YOUR_API_KEY_HERE",
  authDomain: "YOUR_PROJECT.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  appId: "YOUR_APP_ID"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Global variables
window.recaptchaVerifier = null;
window.confirmationResult = null;
window.firebaseInitialized = false;

// Initialize Firebase with reCAPTCHA
function initializeFirebase() {
  try {
    // Check if already initialized
    if (window.firebaseInitialized) {
      return true;
    }
    
    // Create invisible reCAPTCHA
    window.recaptchaVerifier = new RecaptchaVerifier(
      'recaptcha-container',
      {
        'size': 'invisible',
        'callback': (response) => {
          console.log('reCAPTCHA solved:', response);
        },
        'expired-callback': () => {
          console.log('reCAPTCHA expired, resetting...');
          resetRecaptcha();
        }
      },
      auth
    );
    
    // Render reCAPTCHA
    window.recaptchaVerifier.render().then((widgetId) => {
      console.log('reCAPTCHA widget ID:', widgetId);
      window.recaptchaWidgetId = widgetId;
    });
    
    window.firebaseInitialized = true;
    return true;
    
  } catch (error) {
    console.error('Firebase initialization error:', error);
    return false;
  }
}

// Reset reCAPTCHA if needed
function resetRecaptcha() {
  if (window.recaptchaVerifier) {
    window.recaptchaVerifier.clear();
    window.recaptchaVerifier = null;
  }
  window.firebaseInitialized = false;
  initializeFirebase();
}

// Extract phone number from hidden input
function getFullPhoneNumber() {
  const mobileInput = document.getElementById('phoneNumber');
  const hiddenMobile = document.getElementById('fullMobile');
  
  if (hiddenMobile && hiddenMobile.value) {
    return hiddenMobile.value;
  }
  
  if (mobileInput && mobileInput.value) {
    // Add +91 if not present
    let phone = mobileInput.value.replace(/\D/g, '');
    if (phone.length === 10) {
      return '+91' + phone;
    }
  }
  
  return null;
}

// Send OTP function - UPDATED FOR NEW TEMPLATE
window.sendOTP = function () {
  // Initialize Firebase first
  if (!initializeFirebase()) {
    alert('Firebase initialization failed. Please refresh the page.');
    return;
  }
  
  // Get phone number from hidden input
  const phone = getFullPhoneNumber();
  
  if (!phone) {
    alert('Please enter a valid mobile number');
    return;
  }
  
  // Format check
  if (!phone.startsWith("+91")) {
    alert("Please enter Indian mobile number (+91XXXXXXXXXX)");
    return;
  }
  
  if (phone.length !== 13) { // +91 + 10 digits
    alert("Please enter a valid 10-digit mobile number");
    return;
  }
  
  // Show loading state
  const sendBtn = document.getElementById('sendOtpBtn');
  const btnText = document.getElementById('btnText');
  const btnLoading = document.getElementById('btnLoading');
  
  if (sendBtn && btnText && btnLoading) {
    btnText.classList.add('hidden');
    btnLoading.classList.remove('hidden');
    sendBtn.disabled = true;
  }
  
  // Send OTP using Firebase
  signInWithPhoneNumber(auth, phone, window.recaptchaVerifier)
    .then((confirmationResult) => {
      window.confirmationResult = confirmationResult;
      
      // Show success message in template alert
      const alertSuccess = document.getElementById('alertSuccess');
      if (alertSuccess) {
        alertSuccess.querySelector('span').textContent = 'OTP sent successfully! Check your phone.';
        alertSuccess.classList.remove('hidden');
        
        // Auto hide after 5 seconds
        setTimeout(() => {
          alertSuccess.classList.add('hidden');
        }, 5000);
      }
      
      // Move to step 2 (OTP entry)
      if (typeof goToStep === 'function') {
        goToStep(2);
      }
      
      // Start OTP timer if function exists
      if (typeof startTimer === 'function') {
        startTimer();
      }
      
    })
    .catch((error) => {
      console.error("Firebase OTP error:", error);
      
      // Handle specific errors
      let errorMessage = "Failed to send OTP. ";
      
      switch (error.code) {
        case 'auth/invalid-phone-number':
          errorMessage += "Invalid phone number format.";
          break;
        case 'auth/quota-exceeded':
          errorMessage += "SMS quota exceeded. Please try again later.";
          break;
        case 'auth/too-many-requests':
          errorMessage += "Too many requests. Please try again later.";
          break;
        case 'auth/operation-not-allowed':
          errorMessage += "Phone authentication is not enabled in Firebase console.";
          break;
        default:
          errorMessage += error.message || "Please try again.";
      }
      
      // Show error in template alert
      const alertError = document.getElementById('alertError');
      if (alertError) {
        document.getElementById('errorText').textContent = errorMessage;
        alertError.classList.remove('hidden');
        
        // Auto hide after 5 seconds
        setTimeout(() => {
          alertError.classList.add('hidden');
        }, 5000);
      } else {
        alert(errorMessage);
      }
      
      // Reset reCAPTCHA on error
      resetRecaptcha();
      
    })
    .finally(() => {
      // Reset button state
      if (sendBtn && btnText && btnLoading) {
        btnText.classList.remove('hidden');
        btnLoading.classList.add('hidden');
        sendBtn.disabled = false;
      }
    });
};

// Verify OTP function - UPDATED FOR NEW TEMPLATE
window.verifyOTP = function () {
  // Get OTP from combined input or individual boxes
  let otp = '';
  
  // Try to get OTP from hidden input first
  const otpHidden = document.getElementById('otp');
  if (otpHidden && otpHidden.value) {
    otp = otpHidden.value;
  } else {
    // Try to get from individual OTP boxes
    for (let i = 1; i <= 6; i++) {
      const otpBox = document.getElementById('otp' + i);
      if (otpBox && otpBox.value) {
        otp += otpBox.value;
      }
    }
  }
  
  if (!otp || otp.length !== 6) {
    alert("Please enter a valid 6-digit OTP");
    return;
  }
  
  // Show loading state
  const resetBtn = document.getElementById('resetBtn');
  const resetBtnText = document.getElementById('resetBtnText');
  const resetBtnLoading = document.getElementById('resetBtnLoading');
  
  if (resetBtn && resetBtnText && resetBtnLoading) {
    resetBtnText.classList.add('hidden');
    resetBtnLoading.classList.remove('hidden');
    resetBtn.disabled = true;
  }
  
  // Verify OTP with Firebase
  window.confirmationResult.confirm(otp)
    .then((result) => {
      // OTP verified successfully
      console.log("OTP verified successfully:", result);
      
      // Check passwords match before submitting
      const password = document.getElementById('password')?.value;
      const confirmPassword = document.getElementById('confirmPassword')?.value;
      
      if (!password || password.length < 6) {
        alert("Password must be at least 6 characters");
        return;
      }
      
      if (password !== confirmPassword) {
        alert("Passwords do not match");
        return;
      }
      
      // Show success message
      const alertSuccess = document.getElementById('alertSuccess');
      if (alertSuccess) {
        alertSuccess.querySelector('span').textContent = 'OTP verified! Resetting password...';
        alertSuccess.classList.remove('hidden');
      }
      
      // Submit the form after delay
      setTimeout(() => {
        document.getElementById('resetForm').submit();
      }, 1000);
      
    })
    .catch((error) => {
      console.error("OTP verification error:", error);
      
      let errorMessage = "Invalid OTP. ";
      
      switch (error.code) {
        case 'auth/invalid-verification-code':
          errorMessage += "The OTP code is invalid.";
          break;
        case 'auth/code-expired':
          errorMessage += "The OTP code has expired. Please request a new one.";
          break;
        default:
          errorMessage += "Please try again.";
      }
      
      // Show error in template alert
      const alertError = document.getElementById('alertError');
      if (alertError) {
        document.getElementById('errorText').textContent = errorMessage;
        alertError.classList.remove('hidden');
        
        // Auto hide after 5 seconds
        setTimeout(() => {
          alertError.classList.add('hidden');
        }, 5000);
      } else {
        alert(errorMessage);
      }
      
    })
    .finally(() => {
      // Reset button state
      if (resetBtn && resetBtnText && resetBtnLoading) {
        resetBtnText.classList.remove('hidden');
        resetBtnLoading.classList.add('hidden');
        resetBtn.disabled = false;
      }
    });
};

// Resend OTP function
window.resendOTP = function () {
  // Use the same sendOTP function
  window.sendOTP();
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  // Initialize Firebase
  setTimeout(() => {
    initializeFirebase();
  }, 1000);
  
  // Test mode notification
  console.log('Firebase OTP system initialized');
  console.log('For testing, use phone: +911234567890 and OTP: 123456');
});

// Export for testing
window.firebaseAuth = auth;