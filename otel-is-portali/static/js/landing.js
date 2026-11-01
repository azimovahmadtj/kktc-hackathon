/* =========================================================
   Otel İş Portalı — Landing Page Interactions
   ========================================================= */
(() => {
  "use strict";

  document.documentElement.classList.add("js");
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
  const img = (id, w = 800) => `https://images.unsplash.com/photo-${id}?w=${w}&q=70&auto=format&fit=crop`;

  /* ---------------- Data ---------------- */
  const JOBS = [
    { id: 1, title: { tr: "Animatör", en: "Animator", ru: "Аниматор" }, dept: "entertainment",
      hotel: "Noah's Ark Deluxe", logo: "NA", city: "Bafra", type: "sezonluk",
      salary: "£1.200", housing: true, meals: true, score: 92, photo: "1540541338287-41700207dee6" },
    { id: 2, title: { tr: "Garson", en: "Waiter / Waitress", ru: "Официант" }, dept: "food_beverage",
      hotel: "Salamis Bay Conti", logo: "SC", city: "Gazimağusa", type: "sezonluk",
      salary: "£1.050", housing: true, meals: true, score: 88, photo: "1414235077428-338989a2e8c0" },
    { id: 3, title: { tr: "Resepsiyonist", en: "Receptionist", ru: "Администратор" }, dept: "front_office",
      hotel: "Kaya Palazzo", logo: "KP", city: "Girne", type: "tam",
      salary: "£1.450", housing: true, meals: true, score: 94, photo: "1564501049412-61c2a3083791" },
    { id: 4, title: { tr: "Aşçı", en: "Cook", ru: "Повар" }, dept: "kitchen",
      hotel: "Elexus Hotel", logo: "EX", city: "Girne", type: "tam",
      salary: "£1.600", housing: false, meals: true, score: 81, photo: "1577219491135-ce391730fb2c" },
    { id: 5, title: { tr: "Kat Görevlisi", en: "Housekeeper", ru: "Горничная" }, dept: "housekeeping",
      hotel: "Merit Lefkoşa", logo: "MR", city: "Lefkoşa", type: "tam",
      salary: null, housing: true, meals: true, score: 86, photo: "1590490360182-c33d57733427" },
    { id: 6, title: { tr: "Barmen", en: "Bartender", ru: "Бармен" }, dept: "food_beverage",
      hotel: "Acapulco Resort", logo: "AC", city: "Girne", type: "sezonluk",
      salary: "£1.150", housing: true, meals: false, score: 79, photo: "1517248135467-4c7edcad34c4" },
  ];

  // Real job ads from Django (json_script). Falls back to the demo list above if the database is empty.
  const REGISTER_URL = "/register/";
  const DEPT_PHOTO = {
    front_office: "1564501049412-61c2a3083791", food_beverage: "1414235077428-338989a2e8c0", kitchen: "1577219491135-ce391730fb2c",
    housekeeping: "1590490360182-c33d57733427", entertainment: "1540541338287-41700207dee6", spa: "1544161515-4ab6ce6db874",
    technical: "1542314831-068cd1dbfeeb",
  };
  try {
    const server = JSON.parse(document.getElementById("jobs-data")?.textContent || "[]");
    if (server.length) {
      JOBS.length = 0;
      server.forEach((j) => JOBS.push({
        ...j,
        title: { tr: j.title, en: j.title, ru: j.title },
        type: j.type === "seasonal" ? "sezonluk" : "tam",
        photo: DEPT_PHOTO[j.dept] || "1566073771259-6a8506099945",
      }));
    }
  } catch { /* keep demo data */ }

  const DEPT = {
    tr: { front_office: "Ön Büro", food_beverage: "Yiyecek & İçecek", kitchen: "Mutfak", housekeeping: "Housekeeping", entertainment: "Animasyon", spa: "Spa & Wellness", technical: "Teknik Servis" },
    en: { front_office: "Front Office", food_beverage: "Food & Beverage", kitchen: "Kitchen", housekeeping: "Housekeeping", entertainment: "Entertainment", spa: "Spa & Wellness", technical: "Technical Service" },
    ru: { front_office: "Ресепшн", food_beverage: "Ресторан и бар", kitchen: "Кухня", housekeeping: "Хаускипинг", entertainment: "Анимация", spa: "Спа и велнес", technical: "Техническая служба" },
  };

  /* ---------------- i18n ---------------- */
  const I18N = {
    tr: {
      "nav.home": "Ana Sayfa", "nav.jobs": "İş İlanları", "nav.how": "Nasıl Çalışır?", "nav.hotels": "Oteller", "nav.about": "Hakkımızda",
      "nav.login": "Giriş Yap", "nav.register": "Kayıt Ol", "nav.panel": "Panelim",
      "hero.badge": "2026 sezonu için 1.240+ yeni ilan yayında",
      "hero.title": "Kuzey Kıbrıs'ta <span class=\"text-gradient\">Hayalinizdeki İşi</span> Keşfedin!",
      "hero.subtitle": "Turizm sektörünün en iyi otellerinde ve restoranlarında size uygun kariyer fırsatlarını keşfedin.",
      "hero.cta1": "İş İlanlarını Keşfet", "hero.cta2": "İşveren Olarak Katıl", "hero.trust": "18.000+ aday bizimle iş buldu",
      "match.label": "Yeni eşleşme", "match.c1": "İngilizce · Rusça", "match.c2": "3 yıl deneyim", "match.c3": "Konaklama + Yemek", "match.btn": "Hemen Başvur",
      "toast.title": "Başvurunuz görüldü",
      "search.posLabel": "Pozisyon", "search.posPh": "Pozisyon veya anahtar kelime", "search.deptLabel": "Departman", "search.all": "Tüm Departmanlar",
      "search.cityLabel": "Şehir / Bölge", "search.allCities": "Tüm Bölgeler", "search.btn": "İş Ara", "search.popular": "Popüler:",
      "stats.hotels": "Partner Otel", "stats.jobs": "Aktif İş İlanı", "stats.candidates": "Kayıtlı Aday", "stats.matches": "Başarılı Başvuru",
      "hotels.eyebrow": "Partner Oteller", "hotels.title": "Adanın en seçkin otellerinde çalışın",
      "hotels.lead": "Girne'den Bafra'ya, Kuzey Kıbrıs'ın lüks resort ve butik otelleri ekiplerini Otel İş Portalı üzerinden kuruyor.",
      "hotels.verified": "Doğrulanmış", "hotels.open": "açık pozisyon", "hotels.view": "İlanları Gör",
      "jobs.eyebrow": "Popüler İlanlar", "jobs.title": "Bu hafta en çok başvurulan pozisyonlar",
      "jobs.fAll": "Tümü", "jobs.fSeason": "Sezonluk", "jobs.fFull": "Tam Zamanlı", "jobs.all": "Tüm İlanları Gör",
      "jobs.empty": "Aramanıza uygun ilan bulunamadı. Filtreleri değiştirmeyi deneyin.",
      "job.season": "Sezonluk", "job.full": "Tam Zamanlı", "job.housing": "Konaklama", "job.meals": "Yemek", "job.verified": "Doğrulanmış",
      "job.month": "/ ay", "job.negotiable": "Görüşülür", "job.details": "Detayları Gör", "job.match": "Uyum", "job.save": "Kaydet",
      "how.eyebrow": "Nasıl Çalışır?", "how.title": "Üç adımda yeni işinize başlayın",
      "how.lead": "Karmaşık başvuru süreçlerine son. Profilinizi bir kez oluşturun, gerisini akıllı eşleştirme sistemimize bırakın.",
      "how.s1t": "Profilini Oluştur", "how.s1d": "Kişisel bilgilerini, deneyimini, bildiğin dilleri ekle ve CV'ni yükle. Sadece 3 dakika.",
      "how.s2t": "Sana Uygun İşleri Keşfet", "how.s2d": "Profiline göre hesaplanan uyumluluk skoruyla sana en uygun fırsatları anında gör.",
      "how.s3t": "Hemen Başvur", "how.s3d": "Tek tıkla otellere doğrudan başvur ve başvuru durumunu anlık olarak takip et.",
      "why.eyebrow": "Neden Otel İş Portalı?", "why.title": "Turizm kariyeriniz için tasarlanmış akıllı platform",
      "why.f1t": "Akıllı Aday Eşleştirme", "why.f1d": "Yapay zekâ destekli algoritmamız; deneyim, dil, departman ve tercihlerinizi analiz ederek sizi doğru otelle buluşturur.",
      "why.f2t": "Uyumluluk Skoru", "why.f2d": "Her ilan için beceri ve deneyiminize göre yüzdelik uyum skoru görün.",
      "why.f3t": "Doğrulanmış Oteller", "why.f3d": "Tüm işverenler ekibimiz tarafından tek tek doğrulanır. Sahte ilan yok.",
      "why.f4t": "Konaklama & Yemek Filtresi", "why.f4d": "Lojman ve yemek imkânı sunan ilanları tek tıkla filtreleyin.",
      "why.f5t": "Sezonluk Fırsatlar", "why.f5d": "Yaz sezonu için erken başvurun, en iyi pozisyonları kaçırmayın.",
      "why.f6t": "Başvuru Takip Paneli", "why.f6d": "Tüm başvurularınızı tek ekrandan takip edin: görüldü, mülakat, teklif — her adımda anlık bildirim.",
      "testi.quote": "\"Profilimi oluşturduktan iki gün sonra Girne'deki bir resorttan mülakat daveti aldım. Konaklama ve yemek filtresi sayesinde tam aradığım işi buldum.\"",
      "testi.role": "Resepsiyonist, Kaya Palazzo",
      "cta.title": "Hayalinizdeki Kariyere İlk Adımı Atın!",
      "cta.text": "Ücretsiz profilinizi oluşturun, Kuzey Kıbrıs'ın en iyi otellerinden size özel iş teklifleri almaya başlayın.",
      "cta.btn1": "Hemen Kayıt Ol", "cta.btn2": "İş İlanlarını Gör", "cta.p1": "✓ Tamamen ücretsiz", "cta.p2": "✓ 3 dakikada profil", "cta.p3": "✓ Doğrulanmış işverenler",
      "footer.about": "Kuzey Kıbrıs'ın otel ve turizm sektörüne özel, akıllı eşleştirme destekli işe alım platformu.",
      "footer.platform": "Platform", "footer.employers": "İşverenler İçin", "footer.company": "Kurumsal", "footer.aboutUs": "Hakkımızda",
      "footer.faq": "Sıkça Sorulan Sorular", "footer.privacy": "Gizlilik Politikası", "footer.terms": "Kullanım Koşulları", "footer.contact": "İletişim",
      "footer.nlPh": "E-posta adresiniz", "footer.rights": "Tüm hakları saklıdır.", "footer.made": "Kuzey Kıbrıs'ta ♥ ile tasarlandı",
      "msg.results": (n) => `${n} uygun ilan bulundu`, "msg.none": "Uygun ilan bulunamadı", "msg.saved": "İlan kaydedildi",
      "msg.unsaved": "İlan kayıtlılardan çıkarıldı", "msg.details": "İlan detayları için lütfen giriş yapın", "msg.nl": "Bültene abone oldunuz. Teşekkürler!",
      "msg.soon": "Bu sayfa yakında yayında",
    },
    en: {
      "nav.home": "Home", "nav.jobs": "Jobs", "nav.how": "How It Works", "nav.hotels": "Hotels", "nav.about": "About Us",
      "nav.login": "Sign In", "nav.register": "Sign Up", "nav.panel": "My Dashboard",
      "hero.badge": "1,240+ new openings live for the 2026 season",
      "hero.title": "Discover <span class=\"text-gradient\">Your Dream Job</span> in Northern Cyprus!",
      "hero.subtitle": "Find career opportunities that fit you at the finest hotels and restaurants in the tourism industry.",
      "hero.cta1": "Explore Jobs", "hero.cta2": "Join as an Employer", "hero.trust": "18,000+ candidates found a job with us",
      "match.label": "New match", "match.c1": "English · Russian", "match.c2": "3 years experience", "match.c3": "Housing + Meals", "match.btn": "Apply Now",
      "toast.title": "Your application was viewed",
      "search.posLabel": "Position", "search.posPh": "Position or keyword", "search.deptLabel": "Department", "search.all": "All Departments",
      "search.cityLabel": "City / Region", "search.allCities": "All Regions", "search.btn": "Search", "search.popular": "Popular:",
      "stats.hotels": "Partner Hotels", "stats.jobs": "Active Job Ads", "stats.candidates": "Registered Candidates", "stats.matches": "Successful Applications",
      "hotels.eyebrow": "Partner Hotels", "hotels.title": "Work at the island's finest hotels",
      "hotels.lead": "From Kyrenia to Bafra, Northern Cyprus' luxury resorts and boutique hotels build their teams on Otel İş Portalı.",
      "hotels.verified": "Verified", "hotels.open": "open positions", "hotels.view": "View Jobs",
      "jobs.eyebrow": "Popular Jobs", "jobs.title": "Most applied positions this week",
      "jobs.fAll": "All", "jobs.fSeason": "Seasonal", "jobs.fFull": "Full-time", "jobs.all": "View All Jobs",
      "jobs.empty": "No jobs match your search. Try changing the filters.",
      "job.season": "Seasonal", "job.full": "Full-time", "job.housing": "Housing", "job.meals": "Meals", "job.verified": "Verified",
      "job.month": "/ mo", "job.negotiable": "Negotiable", "job.details": "View Details", "job.match": "Match", "job.save": "Save",
      "how.eyebrow": "How It Works", "how.title": "Start your new job in three steps",
      "how.lead": "No more complicated applications. Create your profile once and let our smart matching do the rest.",
      "how.s1t": "Create Your Profile", "how.s1d": "Add your personal details, experience and languages, and upload your CV. Just 3 minutes.",
      "how.s2t": "Discover Matching Jobs", "how.s2d": "Instantly see the best opportunities ranked by a compatibility score based on your profile.",
      "how.s3t": "Apply Instantly", "how.s3d": "Apply directly to hotels with one click and track your application status in real time.",
      "why.eyebrow": "Why Otel İş Portalı?", "why.title": "A smart platform built for your hospitality career",
      "why.f1t": "Smart Candidate Matching", "why.f1d": "Our AI-powered algorithm analyses your experience, languages, department and preferences to connect you with the right hotel.",
      "why.f2t": "Compatibility Score", "why.f2d": "See a percentage match score for every job based on your skills and experience.",
      "why.f3t": "Verified Hotels", "why.f3d": "Every employer is individually verified by our team. No fake listings.",
      "why.f4t": "Housing & Meals Filter", "why.f4d": "Filter jobs offering accommodation and meals with a single click.",
      "why.f5t": "Seasonal Opportunities", "why.f5d": "Apply early for the summer season and never miss the best positions.",
      "why.f6t": "Application Tracking", "why.f6d": "Track all applications on one screen: viewed, interview, offer — with instant notifications at every step.",
      "testi.quote": "\"Two days after creating my profile I got an interview invitation from a resort in Kyrenia. Thanks to the housing and meals filter I found exactly the job I wanted.\"",
      "testi.role": "Receptionist, Kaya Palazzo",
      "cta.title": "Take the First Step Toward Your Dream Career!",
      "cta.text": "Create your free profile and start receiving personalised job offers from the best hotels in Northern Cyprus.",
      "cta.btn1": "Sign Up Now", "cta.btn2": "Browse Jobs", "cta.p1": "✓ Completely free", "cta.p2": "✓ Profile in 3 minutes", "cta.p3": "✓ Verified employers",
      "footer.about": "A smart-matching recruitment platform dedicated to the hotel and tourism industry of Northern Cyprus.",
      "footer.platform": "Platform", "footer.employers": "For Employers", "footer.company": "Company", "footer.aboutUs": "About Us",
      "footer.faq": "FAQ", "footer.privacy": "Privacy Policy", "footer.terms": "Terms of Service", "footer.contact": "Contact",
      "footer.nlPh": "Your email address", "footer.rights": "All rights reserved.", "footer.made": "Designed with ♥ in Northern Cyprus",
      "msg.results": (n) => `${n} matching job${n === 1 ? "" : "s"} found`, "msg.none": "No matching jobs found", "msg.saved": "Job saved",
      "msg.unsaved": "Job removed from saved", "msg.details": "Please sign in to view job details", "msg.nl": "You're subscribed. Thank you!",
      "msg.soon": "This page is coming soon",
    },
    ru: {
      "nav.home": "Главная", "nav.jobs": "Вакансии", "nav.how": "Как это работает", "nav.hotels": "Отели", "nav.about": "О нас",
      "nav.login": "Войти", "nav.register": "Регистрация", "nav.panel": "Мой кабинет",
      "hero.badge": "Более 1 240 новых вакансий на сезон 2026",
      "hero.title": "Найдите <span class=\"text-gradient\">работу мечты</span> на Северном Кипре!",
      "hero.subtitle": "Откройте подходящие карьерные возможности в лучших отелях и ресторанах туристической отрасли.",
      "hero.cta1": "Смотреть вакансии", "hero.cta2": "Для работодателей", "hero.trust": "18 000+ кандидатов нашли работу с нами",
      "match.label": "Новое совпадение", "match.c1": "Английский · Русский", "match.c2": "Опыт 3 года", "match.c3": "Жильё + питание", "match.btn": "Откликнуться",
      "toast.title": "Ваш отклик просмотрен",
      "search.posLabel": "Должность", "search.posPh": "Должность или ключевое слово", "search.deptLabel": "Отдел", "search.all": "Все отделы",
      "search.cityLabel": "Город / Регион", "search.allCities": "Все регионы", "search.btn": "Найти", "search.popular": "Популярное:",
      "stats.hotels": "Отелей-партнёров", "stats.jobs": "Активных вакансий", "stats.candidates": "Кандидатов", "stats.matches": "Успешных откликов",
      "hotels.eyebrow": "Отели-партнёры", "hotels.title": "Работайте в лучших отелях острова",
      "hotels.lead": "От Кирении до Бафры — люксовые курорты и бутик-отели Северного Кипра собирают команды через Otel İş Portalı.",
      "hotels.verified": "Проверено", "hotels.open": "вакансий", "hotels.view": "Вакансии",
      "jobs.eyebrow": "Популярные вакансии", "jobs.title": "Самые востребованные позиции недели",
      "jobs.fAll": "Все", "jobs.fSeason": "Сезонные", "jobs.fFull": "Полный день", "jobs.all": "Все вакансии",
      "jobs.empty": "По вашему запросу ничего не найдено. Попробуйте изменить фильтры.",
      "job.season": "Сезонная", "job.full": "Полный день", "job.housing": "Жильё", "job.meals": "Питание", "job.verified": "Проверено",
      "job.month": "/ мес", "job.negotiable": "Договорная", "job.details": "Подробнее", "job.match": "Совпадение", "job.save": "Сохранить",
      "how.eyebrow": "Как это работает", "how.title": "Новая работа в три шага",
      "how.lead": "Никаких сложных откликов. Создайте профиль один раз — остальное сделает умный подбор.",
      "how.s1t": "Создайте профиль", "how.s1d": "Добавьте личные данные, опыт, языки и загрузите резюме. Всего 3 минуты.",
      "how.s2t": "Находите подходящие вакансии", "how.s2d": "Сразу видите лучшие предложения с оценкой совместимости по вашему профилю.",
      "how.s3t": "Откликайтесь сразу", "how.s3d": "Откликайтесь в отели в один клик и отслеживайте статус в реальном времени.",
      "why.eyebrow": "Почему Otel İş Portalı?", "why.title": "Умная платформа для карьеры в гостеприимстве",
      "why.f1t": "Умный подбор кандидатов", "why.f1d": "Алгоритм на базе ИИ анализирует опыт, языки, отдел и предпочтения и находит для вас подходящий отель.",
      "why.f2t": "Оценка совместимости", "why.f2d": "Процент совпадения для каждой вакансии на основе ваших навыков и опыта.",
      "why.f3t": "Проверенные отели", "why.f3d": "Каждый работодатель проверяется нашей командой. Никаких фейковых вакансий.",
      "why.f4t": "Фильтр жилья и питания", "why.f4d": "Вакансии с проживанием и питанием — в один клик.",
      "why.f5t": "Сезонные вакансии", "why.f5d": "Откликайтесь заранее на летний сезон и не упускайте лучшие позиции.",
      "why.f6t": "Отслеживание откликов", "why.f6d": "Все отклики на одном экране: просмотрено, собеседование, оффер — с мгновенными уведомлениями.",
      "testi.quote": "«Через два дня после создания профиля меня пригласили на собеседование в курорт в Кирении. Благодаря фильтру жилья и питания я нашла именно то, что искала.»",
      "testi.role": "Администратор, Kaya Palazzo",
      "cta.title": "Сделайте первый шаг к карьере мечты!",
      "cta.text": "Создайте бесплатный профиль и получайте персональные предложения от лучших отелей Северного Кипра.",
      "cta.btn1": "Зарегистрироваться", "cta.btn2": "Смотреть вакансии", "cta.p1": "✓ Полностью бесплатно", "cta.p2": "✓ Профиль за 3 минуты", "cta.p3": "✓ Проверенные работодатели",
      "footer.about": "Платформа подбора персонала с умным мэтчингом для гостиничной и туристической отрасли Северного Кипра.",
      "footer.platform": "Платформа", "footer.employers": "Работодателям", "footer.company": "Компания", "footer.aboutUs": "О нас",
      "footer.faq": "Вопросы и ответы", "footer.privacy": "Политика конфиденциальности", "footer.terms": "Условия использования", "footer.contact": "Контакты",
      "footer.nlPh": "Ваш e-mail", "footer.rights": "Все права защищены.", "footer.made": "Создано с ♥ на Северном Кипре",
      "msg.results": (n) => `Найдено вакансий: ${n}`, "msg.none": "Подходящих вакансий нет", "msg.saved": "Вакансия сохранена",
      "msg.unsaved": "Вакансия удалена из сохранённых", "msg.details": "Войдите, чтобы увидеть детали вакансии", "msg.nl": "Вы подписаны. Спасибо!",
      "msg.soon": "Эта страница скоро появится",
    },
  };

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
  };

  // The server (Django LocaleMiddleware) decides the language and writes it to <html lang>.
  let lang = document.documentElement.lang || "tr";
  if (!I18N[lang]) lang = "tr";
  const t = (key, ...args) => {
    const v = I18N[lang][key] ?? I18N.tr[key] ?? key;
    return typeof v === "function" ? v(...args) : v;
  };

  const state = { type: "all", q: "", dept: "", city: "", saved: new Set(JSON.parse(store.get("oip-saved") || "[]")) };

  /* ---------------- Snackbar ---------------- */
  const snackbar = $("#snackbar");
  let snackTimer;
  function notify(msg) {
    snackbar.textContent = msg;
    snackbar.classList.add("is-visible");
    clearTimeout(snackTimer);
    snackTimer = setTimeout(() => snackbar.classList.remove("is-visible"), 2600);
  }

  /* ---------------- Job cards ---------------- */
  const grid = $("#jobsGrid");
  const icon = {
    pin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>',
    clock: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    heart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>',
  };

  function renderJobs() {
    grid.innerHTML = JOBS.map((j) => {
      const saved = state.saved.has(j.id);
      const typeLabel = j.type === "sezonluk" ? t("job.season") : t("job.full");
      return `
      <article class="job-card reveal is-visible" data-id="${j.id}" data-type="${j.type}">
        <div class="job-card__media">
          <img src="${img(j.photo, 600)}" alt="${j.hotel}" loading="lazy" decoding="async" width="600" height="340" />
          <span class="job-card__type ${j.type === "sezonluk" ? "season" : ""}">${typeLabel}</span>
          <button class="job-card__save" aria-pressed="${saved}" aria-label="${t("job.save")}: ${j.title[lang]}">${icon.heart}</button>
          <div class="job-card__hotel"><span class="job-card__logo">${j.logo}</span>${j.hotel}</div>
        </div>
        <div class="job-card__body">
          <div class="job-card__top">
            <div>
              <h3>${j.title[lang]}</h3>
              <p class="job-card__dept">${DEPT[lang][j.dept]}</p>
            </div>
            ${j.score == null ? "" : `<div class="ring" style="--p:${j.score}" title="${t("job.match")}: ${j.score}%" aria-label="${t("job.match")} ${j.score}%"><span>${j.score}%</span></div>`}
          </div>
          <div class="job-card__meta">
            <span>${icon.pin}${j.city}, KKTC</span>
            <span>${icon.clock}${typeLabel}</span>
          </div>
          <div class="job-card__perks">
            ${j.housing ? `<span class="perk">🏠 ${t("job.housing")}</span>` : ""}
            ${j.meals ? `<span class="perk">🍽 ${t("job.meals")}</span>` : ""}
            <span class="perk perk--green">✓ ${t("job.verified")}</span>
          </div>
          <div class="job-card__foot">
            <p class="salary">${j.salary ? `${j.salary} <small>${t("job.month")}</small>` : `<small>${t("job.negotiable")}</small>`}</p>
            <a class="btn btn--primary" href="${j.url || REGISTER_URL}">${t("job.details")}</a>
          </div>
        </div>
      </article>`;
    }).join("");
    applyFilters(false);
  }

  const norm = (s) => s.toLocaleLowerCase("tr").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i");

  function applyFilters(announce) {
    const q = norm(state.q.trim());
    let visible = 0;
    JOBS.forEach((j) => {
      const card = grid.querySelector(`[data-id="${j.id}"]`);
      const haystack = norm([j.title.tr, j.title.en, j.title.ru, j.hotel, DEPT.tr[j.dept], DEPT.en[j.dept]].join(" "));
      const ok =
        (state.type === "all" || j.type === state.type) &&
        (!q || haystack.includes(q)) &&
        (!state.dept || j.dept === state.dept) &&
        (!state.city || j.city === state.city);
      card.classList.toggle("is-hidden", !ok);
      if (ok) visible++;
    });
    $("#jobsEmpty").hidden = visible > 0;
    if (announce) notify(visible ? t("msg.results", visible) : t("msg.none"));
  }

  grid.addEventListener("click", (e) => {
    const card = e.target.closest(".job-card");
    if (!card) return;
    const id = Number(card.dataset.id);
    const saveBtn = e.target.closest(".job-card__save");
    if (saveBtn) {
      const on = !state.saved.has(id);
      on ? state.saved.add(id) : state.saved.delete(id);
      saveBtn.setAttribute("aria-pressed", on);
      store.set("oip-saved", JSON.stringify([...state.saved]));
      notify(on ? t("msg.saved") : t("msg.unsaved"));
    }
  });

  // Type filter tabs
  $$(".filter").forEach((btn) =>
    btn.addEventListener("click", () => {
      $$(".filter").forEach((b) => { b.classList.remove("is-active"); b.setAttribute("aria-selected", "false"); });
      btn.classList.add("is-active");
      btn.setAttribute("aria-selected", "true");
      state.type = btn.dataset.filter;
      applyFilters(false);
    })
  );

  // Search form
  // Submits to the Django job market (/jobs/?q=&department=&city=)
  const form = $("#searchForm");
  $$("[data-quick]").forEach((chip) =>
    chip.addEventListener("click", () => {
      form.q.value = chip.dataset.quick;
      form.requestSubmit();
    })
  );

  /* ---------------- Apply language ---------------- */
  function applyLang(next) {
    lang = next;
    store.set("oip-lang", lang);
    document.documentElement.lang = lang;
    $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    $$("[data-i18n-html]").forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
    $$("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
    $$("#dept option[value]").forEach((o) => { if (o.value) o.textContent = DEPT[lang][o.value]; });
    $("#langCurrent").textContent = lang.toUpperCase();
    $$(".lang__list [data-lang]").forEach((b) => b.setAttribute("aria-selected", b.dataset.lang === lang));
    renderJobs();
  }

  const langEl = $("#lang");
  const langBtn = $("#langBtn");
  const closeLang = () => { langEl.classList.remove("is-open"); langBtn.setAttribute("aria-expanded", "false"); };
  langBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = langEl.classList.toggle("is-open");
    langBtn.setAttribute("aria-expanded", open);
  });
  $$(".lang__list [data-lang]").forEach((b) =>
    b.addEventListener("click", () => {
      const f = $("#setLangForm");
      if (f) { f.language.value = b.dataset.lang; f.submit(); return; } // Django saves the choice (cookie)
      applyLang(b.dataset.lang); closeLang();
    })
  );
  document.addEventListener("click", (e) => { if (!langEl.contains(e.target)) closeLang(); });

  /* ---------------- Header & mobile menu ---------------- */
  const header = $("#header");
  const toggle = $("#navToggle");
  const toTop = $("#toTop");

  const setMenu = (open) => {
    header.classList.toggle("menu-open", open);
    toggle.setAttribute("aria-expanded", open);
    toggle.setAttribute("aria-label", open ? "Menüyü kapat" : "Menüyü aç");
    document.body.style.overflow = open ? "hidden" : "";
  };
  toggle.addEventListener("click", () => setMenu(!header.classList.contains("menu-open")));
  $$(".nav__menu a").forEach((a) => a.addEventListener("click", () => setMenu(false)));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { setMenu(false); closeLang(); }
  });
  window.addEventListener("resize", () => { if (window.innerWidth > 1024) setMenu(false); });

  // Only touch the DOM when a threshold is actually crossed, at most once per frame
  let ticking = false, lastScrolled = null, lastTop = null;
  const onScroll = () => {
    ticking = false;
    const y = window.scrollY;
    const scrolled = y > 40, top = y > 700;
    if (scrolled !== lastScrolled) { header.classList.toggle("is-scrolled", scrolled); lastScrolled = scrolled; }
    if (top !== lastTop) { toTop.classList.toggle("is-visible", top); lastTop = top; }
  };
  window.addEventListener("scroll", () => {
    if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
  onScroll();

  // Pause hero animations while the hero is off screen
  const hero = $("#hero");
  new IntersectionObserver(([en]) => hero.classList.toggle("is-offscreen", !en.isIntersecting)).observe(hero);
  toTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));

  // Active nav link on scroll
  const links = $$(".nav__link");
  const sectionObs = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        links.forEach((l) => l.classList.toggle("is-active", l.getAttribute("href") === `#${entry.target.id}`));
      });
    },
    { rootMargin: "-45% 0px -50% 0px" }
  );
  ["hero", "jobs", "how", "hotels", "about"].forEach((id) => { const s = document.getElementById(id); if (s) sectionObs.observe(s); });

  /* ---------------- Reveal on scroll ---------------- */
  const revealObs = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        obs.unobserve(entry.target);
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
  );
  // Stagger siblings (one pass per parent)
  const groups = new Map();
  $$(".reveal").forEach((el) => {
    const i = groups.get(el.parentElement) || 0;
    groups.set(el.parentElement, i + 1);
    el.style.setProperty("--d", `${Math.min(i, 6) * 0.08}s`);
    revealObs.observe(el);
  });

  /* ---------------- Counters ---------------- */
  const locale = () => ({ tr: "tr-TR", en: "en-US", ru: "ru-RU" }[lang]);
  const counterObs = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        const target = Number(el.dataset.target);
        const dur = 1800;
        const start = performance.now();
        const tick = (now) => {
          const p = Math.min((now - start) / dur, 1);
          const eased = 1 - Math.pow(1 - p, 4);
          el.textContent = Math.round(target * eased).toLocaleString(locale());
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
        obs.unobserve(el);
      });
    },
    { threshold: 0.5 }
  );
  $$(".counter").forEach((c) => counterObs.observe(c));

  /* ---------------- Misc ---------------- */
  $("#newsletter").addEventListener("submit", (e) => {
    e.preventDefault();
    e.target.reset();
    notify(t("msg.nl"));
  });
  $$('a[href="#"]').forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); notify(t("msg.soon")); }));

  // Hide broken images gracefully (gradient placeholder shows behind)
  document.addEventListener("error", (e) => {
    if (e.target.tagName === "IMG") e.target.style.visibility = "hidden";
  }, true);

  $("#year").textContent = new Date().getFullYear();

  applyLang(lang);
})();
