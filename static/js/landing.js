// landing.js
// 케빈샘랩 랜딩 페이지 인터랙션

(function () {
  'use strict';

  // ── Navbar scroll effect ──
  const navbar = document.getElementById('navbar');
  function handleNavbarScroll() {
    if (window.scrollY > 60) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  }
  window.addEventListener('scroll', handleNavbarScroll, { passive: true });
  handleNavbarScroll();

  // ── Mobile menu toggle ──
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const mobileMenu = document.getElementById('mobileMenu');
  const menuIcon = document.getElementById('menuIcon');
  let menuOpen = false;

  mobileMenuBtn.addEventListener('click', function () {
    menuOpen = !menuOpen;
    mobileMenu.classList.toggle('hidden', !menuOpen);
    menuIcon.setAttribute(
      'd',
      menuOpen
        ? 'M6 18L18 6M6 6l12 12'
        : 'M4 6h16M4 12h16M4 18h16'
    );
  });

  // Close mobile menu on link click
  document.querySelectorAll('.mobile-link').forEach(function (link) {
    link.addEventListener('click', function () {
      menuOpen = false;
      mobileMenu.classList.add('hidden');
      menuIcon.setAttribute('d', 'M4 6h16M4 12h16M4 18h16');
    });
  });

  // ── Smooth scroll for anchor links ──
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      var targetId = this.getAttribute('href');
      if (targetId === '#') return;
      var target = document.querySelector(targetId);
      if (target) {
        e.preventDefault();
        var offsetTop = target.getBoundingClientRect().top + window.pageYOffset - 80;
        window.scrollTo({ top: offsetTop, behavior: 'smooth' });
      }
    });
  });

  // ── Intersection Observer for fade-in animations ──
  var fadeElements = document.querySelectorAll('.fade-up');
  if ('IntersectionObserver' in window) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    );
    fadeElements.forEach(function (el) {
      observer.observe(el);
    });
  } else {
    // Fallback: show all immediately
    fadeElements.forEach(function (el) {
      el.classList.add('visible');
    });
  }
})();

// ── Accordion toggle ──
function toggleAccordion(btn) {
  var item = btn.closest('.accordion-item');
  var content = item.querySelector('.accordion-content');
  var arrow = btn.querySelector('.accordion-arrow');
  var isOpen = content.classList.contains('open');

  // Close all others
  document.querySelectorAll('.accordion-content.open').forEach(function (el) {
    el.classList.remove('open');
    el.closest('.accordion-item')
      .querySelector('.accordion-arrow')
      .style.transform = 'rotate(0deg)';
  });

  // Toggle current
  if (!isOpen) {
    content.classList.add('open');
    arrow.style.transform = 'rotate(180deg)';
  }
}

// ── Toast notification ──
function showToast(message) {
  var toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(function () {
    toast.classList.remove('show');
  }, 3000);
}
