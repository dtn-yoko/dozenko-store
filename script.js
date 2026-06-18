/* =====================================================
   DOZENKO — script.js v2
   Google Sheets + All Interactions
   ===================================================== */

// ===== CRM CONFIG =====
const CRM_API_BASE = 'https://dozenko-crm.loca.lt';
const CRM_FETCH_HEADERS = { 'bypass-tunnel-reminder': '1' };

// ===== GOOGLE SHEETS CONFIG =====
const GOOGLE_SHEET_URL = 'https://script.google.com/macros/s/AKfycbzEhMyargcqODgUhuiQu3J5F-47uB8X_wOOGARLaLanBcii_vdpxfTK_caVmTDhYts7Zg/exec';

// ===== NAVBAR SCROLL =====
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 60);
  const floatBtn = document.getElementById('floating-order-btn');
  if (floatBtn) floatBtn.style.display = window.scrollY > 400 ? 'block' : 'none';
}, { passive: true });

// ===== MOBILE NAV TOGGLE =====
const navToggle = document.getElementById('nav-toggle');
const navLinks  = document.getElementById('nav-links');

navToggle.addEventListener('click', () => {
  navLinks.classList.toggle('open');
  const spans = navToggle.querySelectorAll('span');
  const isOpen = navLinks.classList.contains('open');
  spans[0].style.transform = isOpen ? 'rotate(45deg) translate(5px, 5px)' : '';
  spans[1].style.opacity   = isOpen ? '0' : '';
  spans[2].style.transform = isOpen ? 'rotate(-45deg) translate(5px, -5px)' : '';
});

navLinks.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    navLinks.classList.remove('open');
    navToggle.querySelectorAll('span').forEach(s => {
      s.style.transform = ''; s.style.opacity = '';
    });
  });
});

// ===== HERO COLOR SWITCHER =====
const colorMap = {
  blue:   { src: 'images/rug-blue.jpg',   alt: 'Ocean Blue Flower Rug' },
  green:  { src: 'images/rug-green.jpg',  alt: 'Forest Green Flower Rug' },
  orange: { src: 'images/rug-orange.jpg', alt: 'Caramel Sunset Flower Rug' },
  brown:  { src: 'images/rug-brown.jpg',  alt: 'Warm Brown Flower Rug' },
};

function switchHeroColor(color, dotId) {
  const heroImg = document.getElementById('hero-main-img');
  document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
  document.getElementById(dotId).classList.add('active');
  heroImg.classList.add('switching');
  setTimeout(() => {
    heroImg.src = colorMap[color].src;
    heroImg.alt = colorMap[color].alt;
    heroImg.classList.remove('switching');
  }, 300);

  // Sync flower canvas palette
  if (window._flowerPaletteSwitch) {
    const paletteMap = { blue: 0, green: 1, orange: 2, brown: 3 };
    window._flowerPaletteSwitch(paletteMap[color] ?? 0);
  }
}

// Auto-cycle hero color
let autoColorCycle = true;
const colorKeys = ['blue', 'green', 'orange', 'brown'];
const dotIds    = ['dot-blue', 'dot-green', 'dot-orange', 'dot-brown'];
let currentColorIdx = 0;

const heroImgWrapper = document.querySelector('.hero-img-wrapper');
if (heroImgWrapper) {
  heroImgWrapper.addEventListener('mouseenter', () => { autoColorCycle = false; });
  heroImgWrapper.addEventListener('mouseleave', () => { autoColorCycle = true; });
}

setInterval(() => {
  if (!autoColorCycle) return;
  currentColorIdx = (currentColorIdx + 1) % colorKeys.length;
  switchHeroColor(colorKeys[currentColorIdx], dotIds[currentColorIdx]);
}, 3500);

// ===== LIFESTYLE SLIDESHOW (GIF effect) =====
let slideIndex = 0;
const slides   = document.querySelectorAll('.gif-slide');
const gifDots  = document.querySelectorAll('.gif-dot');

function goToSlide(idx) {
  slides.forEach(s => s.classList.remove('active'));
  gifDots.forEach(d => d.classList.remove('active'));
  slideIndex = idx;
  if (slides[slideIndex]) slides[slideIndex].classList.add('active');
  if (gifDots[slideIndex]) gifDots[slideIndex].classList.add('active');
}

setInterval(() => {
  goToSlide((slideIndex + 1) % slides.length);
}, 2500);

// ===== FAQ ACCORDION =====
function toggleFaq(id) {
  const item = document.getElementById(id);
  const isOpen = item.classList.contains('open');
  document.querySelectorAll('.faq-item').forEach(el => el.classList.remove('open'));
  if (!isOpen) item.classList.add('open');
}

// ===== PRICING: Set Quantity =====
function setOrderQty(qty) {
  setTimeout(() => {
    const select = document.getElementById('order-quantity');
    if (select) select.value = String(qty);
  }, 300);
}

// ===== SCROLL REVEAL =====
const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        revealObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
);

function setupReveal() {
  document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));
  document.querySelectorAll('.section-header, .order-info, .lifestyle-text, .lifestyle-visual').forEach(el => {
    el.classList.add('reveal');
    revealObserver.observe(el);
  });
}

// ===== ORDER FORM SUBMISSION + GOOGLE SHEETS =====
async function submitOrder(e) {
  e.preventDefault();

  const form       = document.getElementById('order-form');
  const submitBtn  = document.getElementById('submit-order-btn');
  const submitText = document.getElementById('submit-btn-text');
  const success    = document.getElementById('order-success');

  const name    = document.getElementById('customer-name').value.trim();
  const email   = document.getElementById('customer-email').value.trim();
  const phone   = document.getElementById('customer-whatsapp').value.trim();
  const qty     = document.getElementById('order-quantity').value;
  const address = document.getElementById('shipping-address').value.trim();
  const notes   = document.getElementById('order-notes').value.trim();
  const colors  = [...document.querySelectorAll('input[name="colors"]:checked')].map(cb => cb.value);
  const timestamp = new Date().toLocaleString('en-US', { timeZone: 'Asia/Ho_Chi_Minh' });

  if (colors.length === 0) {
    showToast('Please select at least one color!', 'error');
    return;
  }

  const priceMap = { '1': '300000', '2': '500000', '3': '700000', '4': '840000' };
  const price = priceMap[qty] || '300000';

  submitBtn.disabled = true;
  submitText.textContent = 'Sending...';
  submitBtn.style.opacity = '0.7';

  const formData = {
    timestamp, name, email, phone,
    quantity: `${qty} piece(s)`,
    price,
    colors: colors.join(', '),
    address, notes
  };

  if (GOOGLE_SHEET_URL && GOOGLE_SHEET_URL !== 'YOUR_GOOGLE_APPS_SCRIPT_URL_HERE') {
    try {
      await fetch(GOOGLE_SHEET_URL, {
        method: 'POST',
        mode: 'no-cors',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
    } catch (err) {
      console.warn('Google Sheets error:', err);
    }
  }

  const orderData = {
    name,
    phone,
    email,
    address,
    notes,
    colors: colors.join(', '),
    quantity: parseInt(qty, 10),
    amount: parseInt(price, 10),
    status: 'pending'
  };

  try {
    await fetch(`${CRM_API_BASE}/api/customers`, {
      method: 'POST',
      headers: { ...CRM_FETCH_HEADERS, 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, phone, zalo: phone })
    });
  } catch (err) {
    console.warn('Customer create error:', err);
  }

  try {
    const productResponse = await fetch(`${CRM_API_BASE}/api/products`, { headers: CRM_FETCH_HEADERS });
    const products = await productResponse.json();
    const product = products[0];
    if (product) {
      orderData.product_id = product.id;
    }
  } catch (err) {
    console.warn('Product lookup error:', err);
  }

  try {
    const customerResponse = await fetch(`${CRM_API_BASE}/api/customers`, { headers: CRM_FETCH_HEADERS });
    const customers = await customerResponse.json();
    const customer = customers.find(c => c.phone === phone || c.name === name);
    if (customer) {
      orderData.customer_id = customer.id;
    }
  } catch (err) {
    console.warn('Customer lookup error:', err);
  }

  if (orderData.product_id && orderData.customer_id) {
    try {
      await fetch(`${CRM_API_BASE}/api/orders`, {
        method: 'POST',
        headers: { ...CRM_FETCH_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData)
      });
    } catch (err) {
      console.warn('Order create error:', err);
    }
  }

  setTimeout(() => {
    form.style.display = 'none';
    success.style.display = 'block';
    success.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 600);
}

// ===== SEPAY BUTTON: Submit CRM then open QR =====
async function submitOrderAndPay() {
  const form       = document.getElementById('order-form');
  const submitBtn  = document.getElementById('sepay-pay-btn');

  const name    = document.getElementById('customer-name').value.trim();
  const email   = document.getElementById('customer-email').value.trim();
  const phone   = document.getElementById('customer-whatsapp').value.trim();
  const qty     = document.getElementById('order-quantity').value;
  const address = document.getElementById('shipping-address').value.trim();
  const notes   = document.getElementById('order-notes').value.trim();
  const colors  = [...document.querySelectorAll('input[name="colors"]:checked')].map(cb => cb.value);

  // Validate
  if (!name) { showToast('Vui lòng nhập họ tên!', 'error'); return; }
  if (!phone && !email) { showToast('Vui lòng nhập SĐT hoặc email!', 'error'); return; }
  if (colors.length === 0) { showToast('Vui lòng chọn ít nhất 1 màu thảm!', 'error'); return; }
  if (!qty) { showToast('Vui lòng chọn số lượng!', 'error'); return; }
  if (!address) { showToast('Vui lòng nhập địa chỉ giao hàng!', 'error'); return; }

  const priceMap = { '1': '300000', '2': '500000', '3': '700000', '4': '840000' };
  const price = priceMap[qty] || '300000';

  submitBtn.disabled = true;
  submitBtn.textContent = 'Đang xử lý...';

  // 1. Tạo/tìm khách hàng trong CRM
  let customerId = null;
  try {
    await fetch(`${CRM_API_BASE}/api/customers`, {
      method: 'POST',
      headers: { ...CRM_FETCH_HEADERS, 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, phone, zalo: phone })
    });
  } catch (err) { console.warn('Customer create:', err); }

  try {
    const res = await fetch(`${CRM_API_BASE}/api/customers`, { headers: CRM_FETCH_HEADERS });
    const customers = await res.json();
    const found = customers.find(c => c.phone === phone || c.name === name);
    if (found) customerId = found.id;
  } catch (err) { console.warn('Customer lookup:', err); }

  // 2. Lấy product đầu tiên
  let productId = null;
  try {
    const res = await fetch(`${CRM_API_BASE}/api/products`, { headers: CRM_FETCH_HEADERS });
    const products = await res.json();
    if (products[0]) productId = products[0].id;
  } catch (err) { console.warn('Product lookup:', err); }

  // 3. Tạo đơn hàng trong CRM
  if (customerId && productId) {
    try {
      await fetch(`${CRM_API_BASE}/api/orders`, {
        method: 'POST',
        headers: { ...CRM_FETCH_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: customerId,
          product_id: productId,
          amount: parseInt(price, 10),
          status: 'pending'
        })
      });
    } catch (err) { console.warn('Order create:', err); }
  }

  submitBtn.disabled = false;
  submitBtn.textContent = 'Thanh toán ngay bằng SePay';

  // 4. Mở QR Sepay
  const sepayUrl = `https://qr.sepay.vn/img?bank=Vietinbank&acc=100001671497&template=compact&amount=${price}&des=SEVQR`;
  window.open(sepayUrl, '_blank');

  // 5. Hiển thị thông báo
  showToast('Đơn hàng đã được ghi nhận! Vui lòng quét QR để thanh toán.', 'info');
}

// ===== TOAST NOTIFICATION =====
function showToast(msg, type = 'info') {
  const existing = document.querySelector('.toast-msg');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'toast-msg';
  toast.textContent = msg;
  toast.style.cssText = `
    position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
    background: ${type === 'error' ? '#e74c3c' : '#2A4E7C'};
    color: #fff; padding: 12px 24px; border-radius: 40px;
    font-size: 0.88rem; font-weight: 600; z-index: 9999;
    box-shadow: 0 8px 24px rgba(0,0,0,0.2);
    animation: toast-in 0.3s ease;
  `;

  const style = document.createElement('style');
  style.textContent = `@keyframes toast-in { from { opacity:0; transform:translateX(-50%) translateY(20px); } to { opacity:1; transform:translateX(-50%) translateY(0); } }`;
  document.head.appendChild(style);
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ===== SMOOTH SCROLL =====
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', (e) => {
    const target = document.querySelector(link.getAttribute('href'));
    if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  });
});

// ===== PARALLAX HERO =====
window.addEventListener('scroll', () => {
  const scrollY = window.scrollY;
  const s1 = document.querySelector('.shape-1');
  const s2 = document.querySelector('.shape-2');
  if (s1) s1.style.transform = `translateY(${scrollY * 0.15}px)`;
  if (s2) s2.style.transform = `translateY(${scrollY * -0.1}px)`;
}, { passive: true });

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
  setupReveal();
  initFlowerCanvas();
  setupChatWidget();
});

function setupChatWidget() {
  const chatToggle = document.getElementById('chat-toggle');
  const chatPanel = document.getElementById('chat-panel');
  const chatClose = document.getElementById('chat-close');
  const chatMessages = document.getElementById('chat-messages');
  const chatForm = document.getElementById('chat-input-form');
  const chatInput = document.getElementById('chat-input');
  const chatFormBtn = document.getElementById('chat-form-btn');
  const chatSuggestions = document.getElementById('chat-suggestions');

  if (!chatToggle || !chatPanel || !chatMessages || !chatForm || !chatInput || !chatFormBtn || !chatSuggestions) return;

  const chatScript = {
    greeting: 'Chào anh/chị! Em là Dozenko Chat, hỗ trợ tư vấn thảm chân giường nghệ thuật. Anh/chị có thể chọn câu hỏi gợi ý dưới đây hoặc gõ câu hỏi khác, em trả lời ngay.',
    suggestions: [
      'Thảm làm từ chất liệu gì?',
      'Giá 1-2-3 tấm là bao nhiêu?',
      'Kích thước nào phù hợp?',
      'Cách giặt và giữ màu thế nào?'
    ],
    faqs: [
      {
        patterns: ['chất liệu', 'làm từ chất', 'vật liệu', 'sợi cotton'],
        answer: 'Thảm Dozenko làm từ sợi cotton cao cấp, mềm mịn, không gây dị ứng và an toàn cho trẻ em, người lớn lẫn thú cưng. Đế thảm dày 3cm kèm lớp cao su chống trượt, giữ thảm yên khi đi lại.'
      },
      {
        patterns: ['giá', 'mấy tiền', 'bao nhiêu tiền', 'giá bao nhiêu', 'giá bán', 'giá sản phẩm', 'tiền'],
        answer: 'Giá bán hiện tại của Dozenko là: 1 tấm 300.000đ; 2 tấm 500.000đ (miễn phí ship); 3 tấm 700.000đ; 4 tấm 840.000đ. Nếu muốn tiết kiệm, anh/chị có thể chọn combo 2 tấm hoặc 3 tấm để được ưu đãi tốt hơn.',
      },
      {
        patterns: ['kích thước', 'size'],
        answer: 'Kích thước tiêu chuẩn của chúng mình là 50 × 120 cm. Đây là kích thước lý tưởng đặt ở chân giường, lối vào, góc đọc sách hoặc cạnh bồn rửa trong phòng tắm.'
      },
      {
        patterns: ['vệ sinh', 'giặt', 'rửa', 'phai màu'],
        answer: 'Anh/chị có thể lau sạch tại chỗ với xà phòng nhẹ, giặt máy nhẹ ở chế độ cold/warm rồi phơi khô tự nhiên. Tránh sấy máy nhiệt độ cao để giữ họa tiết và màu sắc bền.'
      },
      {
        patterns: ['thú cưng', 'chó', 'mèo', 'pet'],
        answer: 'Hoàn toàn an toàn cho thú cưng. Cotton nhẹ nhàng và đế chống trượt giúp thảm cố định khi chó mèo chạy nhảy. Nếu nhà hay có lông, chọn Nâu Ấm sẽ giúp giấu lông tốt hơn.'
      },
      {
        patterns: ['combo', 'màu khác', 'mix', 'chọn màu'],
        answer: 'Khi mua combo 2/3/4 tấm, anh/chị có thể mix nhiều màu khác nhau. Ví dụ Xanh Đại Dương + Cam Caramel hoặc Nâu Ấm + Xanh Lá Rừng đều rất đẹp.'
      },
      {
        patterns: ['giao hàng', 'ship', 'vận chuyển', 'thời gian'],
        answer: 'Nội thành giao 2-3 ngày, ngoại thành 3-7 ngày tùy khu vực. Combo 2 tấm trở lên thường được miễn phí vận chuyển.'
      },
      {
        patterns: ['đổi trả', 'bảo hành', 'chính sách'],
        answer: 'Chúng mình có đề xuất đổi trả trong 7 ngày nếu sản phẩm lỗi do nhà sản xuất. Ngoài ra, còn có thể hỗ trợ bảo hành 30 ngày với các vấn đề về đường may hoặc đế không đạt chuẩn.'
      },
      {
        patterns: ['đắt', 'giá cao', 'giá'],
        answer: 'Đây là thảm chân giường nghệ thuật, mỗi tấm chọn họa tiết riêng và dùng cotton xịn cùng đế chống trượt dày 3cm. Giá này giúp anh/chị sở hữu sản phẩm đẹp, bền và khác biệt, không phải thảm trang trí đại trà.'
      },
      {
        patterns: ['phòng nhỏ', 'không gian nhỏ', 'nhỏ'],
        answer: 'Rất phù hợp. 50 × 120 cm là kích thước gọn, điển hình dùng cho chân giường đơn, hành lang, lối vào hoặc cạnh sofa. Em cũng có thể tư vấn màu phù hợp ngay nếu anh/chị muốn.'
      }
    ],
    closeOffer: {
      patterns: ['mua', 'đặt', 'ship', 'combo', 'sẵn sàng', 'đơn', 'giá bao nhiêu', 'có ngay', 'tư vấn ngay'],
      answer: 'Em gợi ý anh/chị lấy luôn combo 2 tấm 500.000đ để vừa tiết kiệm, vừa được miễn phí ship. Nếu anh/chị thích tông nhẹ thì Xanh Đại Dương + Xanh Lá Rừng, còn nếu muốn ấm áp thì Nâu Ấm + Cam Caramel rất sang. Mình đặt luôn để giữ giá và ưu đãi hôm nay, anh/chị bấm nút Đặt hàng bên dưới để vào form mua hàng ngay nhé.',
      showFormButton: true
    },
    waitlist: {
      patterns: ['chưa quyết', 'chưa sẵn sàng', 'xem trước', 'tư vấn', 'form', 'thông tin', 'chờ', 'chưa mua'],
      answer: 'Nếu anh/chị chưa quyết được ngay, mình để lại form thông tin giúp em nhé. Em sẽ gửi bộ ảnh mẫu, bảng màu và ưu đãi mới nhất để anh/chị tham khảo.',
      showFormButton: true
    },
    fallback: 'Em chưa rõ lắm, anh/chị có thể chọn câu hỏi gợi ý dưới đây hoặc hỏi em về chất liệu, kích thước, cách giặt. Nếu muốn đặt hàng, anh/chị chỉ cần nói "mua" hoặc "đặt hàng" nhé.'
  };

  let autoGreet = true;
  let userQuestionCount = 0;

  const appendMessage = (text, sender = 'bot') => {
    const message = document.createElement('div');
    message.className = `chat-message ${sender}`;
    message.textContent = text;
    chatMessages.appendChild(message);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  };

  const renderChatSuggestions = () => {
    chatSuggestions.innerHTML = '';
    chatScript.suggestions.forEach((text) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'chat-suggestion-btn';
      button.textContent = text;
      button.addEventListener('click', () => {
        processUserMessage(text);
      });
      chatSuggestions.appendChild(button);
    });
  };

  const showCtaButton = () => {
    chatFormBtn.classList.add('chat-cta-visible');
    chatFormBtn.style.display = 'inline-flex';
  };

  const processUserMessage = (text) => {
    userQuestionCount += 1;
    appendMessage(text, 'user');
    const reply = findAnswer(text);
    setTimeout(() => {
      appendMessage(reply.text, 'bot');
      if (reply.showFormButton || userQuestionCount >= 2) {
        showCtaButton();
      }
    }, 400);
  };

  const openChat = () => {
    chatPanel.hidden = false;
    chatToggle.classList.add('active');
    if (autoGreet) {
      autoGreet = false;
      setTimeout(() => appendMessage(chatScript.greeting, 'bot'), 300);
    }
  };

  const closeChat = () => {
    chatPanel.hidden = true;
    chatToggle.classList.remove('active');
  };

  const shouldShowFormButton = (text) => {
    const normalized = text.toLowerCase();
    return chatScript.closeOffer.patterns.some(p => normalized.includes(p)) || chatScript.waitlist.patterns.some(p => normalized.includes(p));
  };

  const findAnswer = (text) => {
    const normalized = text.toLowerCase();
    for (const faq of chatScript.faqs) {
      if (faq.patterns.some(pattern => normalized.includes(pattern))) {
        return { text: faq.answer, showFormButton: false };
      }
    }

    if (chatScript.closeOffer.patterns.some(p => normalized.includes(p))) {
      return { text: chatScript.closeOffer.answer, showFormButton: true };
    }
    if (chatScript.waitlist.patterns.some(p => normalized.includes(p))) {
      return { text: chatScript.waitlist.answer, showFormButton: true };
    }
    return { text: chatScript.fallback, showFormButton: false };
  };

  chatFormBtn.style.display = 'none';
  renderChatSuggestions();

  chatToggle.addEventListener('click', () => {
    if (chatPanel.hidden) openChat(); else closeChat();
  });

  chatClose.addEventListener('click', closeChat);

  chatForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const value = chatInput.value.trim();
    if (!value) return;
    chatInput.value = '';
    processUserMessage(value);
  });

  chatFormBtn.addEventListener('click', () => {
    closeChat();
    const orderSection = document.getElementById('order');
    if (orderSection) orderSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    else window.location.href = '#order';
  });

  chatToggle.addEventListener('mouseenter', () => chatToggle.style.transform = 'translateY(-1px)');
  chatToggle.addEventListener('mouseleave', () => chatToggle.style.transform = 'translateY(0)');

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    chatToggle.style.transition = 'none';
    chatFormBtn.style.transition = 'none';
  }
}

// =====================================================
// ===== FLOWER CANVAS ANIMATION (GIF-style) =====
// =====================================================
function initFlowerCanvas() {
  const canvas = document.getElementById('flower-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');

  // Color palettes matching the 4 product themes
  const palettes = [
    { petals: ['#2A4E7C', '#4A7BC8', '#6A9CD8', '#8DB8E8'], center: '#FAF8F4', glow: 'rgba(74,123,200,0.35)' },  // Ocean Blue
    { petals: ['#3A6B3A', '#5A9E5A', '#7ABE7A', '#A0D4A0'], center: '#FFF9C4', glow: 'rgba(90,158,90,0.35)' },   // Forest Green
    { petals: ['#C8622A', '#E0823A', '#F2A86A', '#F8C090'], center: '#FFF3E0', glow: 'rgba(200,98,42,0.35)' },    // Caramel Sunset
    { petals: ['#7C3A2A', '#9C5A3A', '#C8906A', '#E0B090'], center: '#FFF8F5', glow: 'rgba(124,58,42,0.35)' },   // Warm Brown
  ];

  let currentPaletteIdx = 0;
  let flowers = [];
  let particles = [];
  let frameCount = 0;
  const CYCLE_FRAMES = 300;

  // Resize canvas to fit wrapper
  function resizeCanvas() {
    const wrapper = canvas.parentElement;
    if (!wrapper) return;
    canvas.width  = wrapper.offsetWidth;
    canvas.height = wrapper.offsetHeight;
  }
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas, { passive: true });

  // ---- Easing ----
  function easeOutElastic(t) {
    if (t === 0 || t === 1) return t;
    return Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * (2 * Math.PI / 4)) + 1;
  }

  // ---- Draw single petal ----
  function drawPetal(ctx, size, color, bloom) {
    const len = size * 0.72 * bloom;
    const w   = size * 0.28 * bloom;
    if (len < 0.5) return;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.bezierCurveTo(-w, -len * 0.3, -w * 0.8, -len * 0.8, 0, -len);
    ctx.bezierCurveTo( w * 0.8, -len * 0.8,  w, -len * 0.3, 0, 0);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, -len);
    grad.addColorStop(0, color + 'CC');
    grad.addColorStop(0.5, color);
    grad.addColorStop(1, color + '66');
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.2)';
    ctx.lineWidth = 0.7;
    ctx.stroke();
  }

  // ---- Flower ----
  class Flower {
    constructor(x, y, size, palette, delay) {
      this.x = x; this.y = y;
      this.targetSize = size;
      this.size = 0;
      this.palette = palette;
      this.petalCount = 6;
      this.rotation = Math.random() * Math.PI * 2;
      this.bloomProgress = 0;
      this.delay = delay || 0;
      this.age = -(this.delay);
      this.lifetime = 200 + Math.random() * 80;
      this.fadeOut = false;
      this.fadeAge = 0;
      this.opacity = 0;
      this.wobble = Math.random() * Math.PI * 2;
      this.wobbleSpeed = 0.018 + Math.random() * 0.012;
    }

    update() {
      this.age++;
      if (this.age < 0) return;

      if (!this.fadeOut) {
        this.bloomProgress = Math.min(1, this.age / 50);
        this.size = this.targetSize * easeOutElastic(this.bloomProgress);
        this.opacity = Math.min(1, this.age / 25);
        if (this.age > this.lifetime) { this.fadeOut = true; this.fadeAge = 0; }
      } else {
        this.fadeAge++;
        this.opacity = Math.max(0, 1 - this.fadeAge / 35);
      }
      this.wobble += this.wobbleSpeed;
    }

    draw(ctx) {
      if (this.age < 0 || this.opacity <= 0 || this.size < 0.5) return;
      ctx.save();
      ctx.globalAlpha = this.opacity * 0.85;
      ctx.translate(this.x, this.y);
      ctx.rotate(this.rotation + Math.sin(this.wobble) * 0.05);

      // Soft glow
      const grd = ctx.createRadialGradient(0, 0, 0, 0, 0, this.size * 1.7);
      grd.addColorStop(0, this.palette.glow);
      grd.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.globalAlpha = this.opacity * 0.3;
      ctx.fillStyle = grd;
      ctx.beginPath(); ctx.arc(0, 0, this.size * 1.7, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = this.opacity * 0.85;

      // Petals
      for (let i = 0; i < this.petalCount; i++) {
        ctx.save();
        ctx.rotate((i / this.petalCount) * Math.PI * 2);
        drawPetal(ctx, this.size, this.palette.petals[i % this.palette.petals.length], this.bloomProgress);
        ctx.restore();
      }

      // Center
      const cg = ctx.createRadialGradient(0, 0, 0, 0, 0, this.size * 0.3);
      cg.addColorStop(0, '#ffffff');
      cg.addColorStop(0.6, this.palette.center);
      cg.addColorStop(1, this.palette.petals[0]);
      ctx.beginPath(); ctx.arc(0, 0, this.size * 0.3, 0, Math.PI * 2);
      ctx.fillStyle = cg; ctx.fill();

      ctx.beginPath(); ctx.arc(0, 0, this.size * 0.12, 0, Math.PI * 2);
      ctx.fillStyle = this.palette.petals[1] || this.palette.petals[0]; ctx.fill();

      ctx.restore();
    }

    isDead() { return this.fadeOut && this.opacity <= 0; }
  }

  // ---- Floating petal particle ----
  class Particle {
    constructor(x, y, palette) {
      this.x = x; this.y = y;
      this.vx = (Math.random() - 0.5) * 1.8;
      this.vy = -Math.random() * 2.5 - 0.5;
      this.size = 3 + Math.random() * 6;
      this.color = palette.petals[Math.floor(Math.random() * palette.petals.length)];
      this.opacity = 0.6 + Math.random() * 0.3;
      this.rotation = Math.random() * Math.PI * 2;
      this.rotSpeed = (Math.random() - 0.5) * 0.14;
      this.gravity = 0.045;
      this.life = 70 + Math.random() * 50;
      this.age = 0;
    }
    update() {
      this.age++; this.vy += this.gravity;
      this.x += this.vx; this.y += this.vy;
      this.rotation += this.rotSpeed;
      this.opacity = Math.max(0, 0.7 * (1 - this.age / this.life));
    }
    draw(ctx) {
      if (this.opacity <= 0) return;
      ctx.save();
      ctx.globalAlpha = this.opacity;
      ctx.translate(this.x, this.y); ctx.rotate(this.rotation);
      ctx.beginPath(); ctx.ellipse(0, 0, this.size, this.size * 0.5, 0, 0, Math.PI * 2);
      ctx.fillStyle = this.color; ctx.fill();
      ctx.restore();
    }
    isDead() { return this.age >= this.life; }
  }

  // ---- Spawn flower cluster ----
  function spawnCluster(palette) {
    const W = canvas.width, H = canvas.height;
    const base = Math.min(W, H);

    const positions = [
      { x: W * 0.25, y: H * 0.27, size: base * 0.14, delay: 0  },
      { x: W * 0.72, y: H * 0.55, size: base * 0.12, delay: 8  },
      { x: W * 0.44, y: H * 0.78, size: base * 0.10, delay: 16 },
      { x: W * 0.12, y: H * 0.62, size: base * 0.055, delay: 22 },
      { x: W * 0.85, y: H * 0.20, size: base * 0.050, delay: 28 },
      { x: W * 0.58, y: H * 0.12, size: base * 0.045, delay: 34 },
      { x: W * 0.35, y: H * 0.48, size: base * 0.038, delay: 38 },
    ];

    positions.forEach(p => flowers.push(new Flower(p.x, p.y, p.size, palette, p.delay)));

    // Burst particles from main flowers
    positions.slice(0, 3).forEach(p => {
      for (let j = 0; j < 7; j++) particles.push(new Particle(p.x, p.y, palette));
    });
  }

  // ---- Expose palette switcher for hero color sync ----
  window._flowerPaletteSwitch = function(idx) {
    if (idx === currentPaletteIdx) return;
    flowers.forEach(f => { if (!f.fadeOut) { f.fadeOut = true; f.fadeAge = 0; } });
    currentPaletteIdx = idx;
    setTimeout(() => spawnCluster(palettes[currentPaletteIdx]), 550);
  };

  // ---- Animation loop ----
  function animate() {
    requestAnimationFrame(animate);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    frameCount++;

    // First frame: spawn
    if (frameCount === 1) spawnCluster(palettes[currentPaletteIdx]);

    // Auto-cycle palette
    if (frameCount % CYCLE_FRAMES === 0) {
      flowers.forEach(f => { if (!f.fadeOut) { f.fadeOut = true; f.fadeAge = 0; } });
      currentPaletteIdx = (currentPaletteIdx + 1) % palettes.length;
      setTimeout(() => spawnCluster(palettes[currentPaletteIdx]), 600);
    }

    // Particles
    particles = particles.filter(p => !p.isDead());
    particles.forEach(p => { p.update(); p.draw(ctx); });

    // Flowers
    flowers = flowers.filter(f => !f.isDead());
    flowers.forEach(f => { f.update(); f.draw(ctx); });
  }

  animate();
}
