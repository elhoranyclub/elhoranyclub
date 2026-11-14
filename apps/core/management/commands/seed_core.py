"""Create/refresh the singleton SiteSettings with realistic defaults.
Pass --demo to also create a demo guardian account (01000000001 / Demo@12345)."""
import datetime
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Dependent, Profile
from apps.core.models import SiteSettings
from apps.events.models import Event
from apps.gallery.models import GalleryAlbum, MediaItem
from apps.memberships.models import Coupon, Membership, MembershipType
from apps.news.models import NewsArticle, NewsCategory, Tag
from apps.pages.models import BoardMember, FAQ, Facility


class Command(BaseCommand):
    help = "Create or update the default SiteSettings row (مركز شباب الحوراني)."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="أيضًا إنشاء حساب تجريبي ولى أمر + تابع")

    def handle(self, *args, **options):
        obj = SiteSettings.load()
        obj.name_ar = "مركز شباب الحوراني"
        obj.name_en = "Al-Hourani Youth Sports Center"
        obj.tagline_ar = "نحو جيل رياضي مبدع"
        obj.tagline_en = "Towards a creative athletic generation"
        obj.phone = "01272833888"
        obj.whatsapp = "01272833888"
        obj.email = "info@hourani-sports.eg"
        obj.address_ar = "الحوراني — مركز ومدينة فارسكور — محافظة دمياط"
        obj.address_en = "Al-Hourani — Faraskour Center & City — Damietta Governorate"
        obj.working_hours_ar = "يوميًا ٧ صباحًا – ١٠ مساءً"
        obj.working_hours_en = "Daily 7:00 AM – 10:00 PM"
        obj.primary_color = "#0e2a47"
        obj.gold_color = "#d4af37"
        obj.green_color = "#146b3a"
        obj.save()
        self.stdout.write(self.style.SUCCESS("SiteSettings جاهزة: مركز شباب الحوراني"))
        if options["demo"]:
            self._seed_demo()

    def _seed_demo(self):
        User = get_user_model()
        user, created = User.objects.get_or_create(phone="01000000001", defaults={"username": "01000000001", "first_name": "أحمد", "last_name": "محمود", "is_active": True})
        if created:
            user.set_password("Demo@12345")
            user.save(update_fields=["password"])
        profile, _created = Profile.objects.get_or_create(
            user=user,
            defaults={
                "full_name_ar": "أحمد محمود الحوراني",
                "full_name_en": "Ahmed Mahmoud Al-Hourani",
                "birth_date": datetime.date(1988, 4, 12),
                "gender": Profile.Gender.MALE,
                "governorate": "القاهرة",
                "address": "الحوراني، مركز فارسكور، دمياط",
                "emergency_contact_name": "منى الحوراني (الزوجة)",
                "emergency_contact_phone": "01000000002",
                "shirt_size": Profile.ShirtSize.XL,
            },
        )
        dep, dep_created = Dependent.objects.get_or_create(
            guardian=user,
            full_name_ar="يوسف أحمد الحوراني",
            birth_date=datetime.date(2017, 9, 3),
            defaults={"gender": Profile.Gender.MALE, "relation": Dependent.Relation.SON, "health_notes": "حساسية من المكسرات"},
        )
        self.stdout.write(self.style.SUCCESS(
            f"Demo OK - {profile.membership_number} | التابع يوسف - {dep.membership_number}\n"
            f"   الدخول: 01000000001 / Demo@12345"
        ))
        self._seed_content(user)
        self._seed_memberships(user, profile, dep)
        self._seed_tournaments(user, dep)
        self._seed_courses(user, dep)
        self._seed_trips(user, dep)
        self._seed_notification_templates()

    def _seed_content(self, author):
        """Phase 2 demo content — real Arabic, references events, idempotent."""
        now = timezone.now()
        # --- News categories
        cat_tournaments, _created = NewsCategory.objects.get_or_create(slug=" بطولات".strip(), defaults={"name_ar": "بطولات", "name_en": "Tournaments"})
        cat_activities, _created = NewsCategory.objects.get_or_create(slug="فعاليات", defaults={"name_ar": "فعاليات", "name_en": "Activities"})
        cat_announce, _created = NewsCategory.objects.get_or_create(slug="إعلانات", defaults={"name_ar": "إعلانات", "name_en": "Announcements"})
        tag_football, _created = Tag.objects.get_or_create(slug="كرة-قدم", defaults={"name": "كرة قدم"})
        tag_swim, _created = Tag.objects.get_or_create(slug="سباحة", defaults={"name": "سباحة"})

        articles = [
            ("بطولة الربيع لكرة القدم الخماسية تنطلق الجمعة", "انطلاق بطولة الربيع للفئات العمرية من 10 حتى 14 سنة بمشاركة 16 فريقًا من مراكز شباب القاهرة الكبرى.", cat_tournaments, [tag_football], True, now - timedelta(days=1)),
            ("فريق السباحة يحصد 3 ذهبيات في بطولة الجمهورية", "أنهى فريق سباحة مركز شباب الحوراني مشاركته في بطولة الجمهورية للبراعم بحصيلة 3 ذهبيات وفضيتين.", cat_tournaments, [tag_swim], True, now - timedelta(days=3)),
            ("يوم مفتوح مجاني في حمام السباحة استعدادًا للصيف", "دعوة مفتوحة لكل أعضاء المركز وأسرهم للاستمتاع بيوم مفتوح في حمام السباحة بمناسبة بداية الصيف.", cat_activities, [tag_swim], False, now - timedelta(days=5)),
            ("بدء تجديد الاشتراكات السنوية للموسم 2026/2027", "يُعلن المركز عن فتح باب تجديد الاشتراكات السنوية مع خصم 20٪ لطلاب المدارس بإيصال المدرسة.", cat_announce, [], False, now - timedelta(days=7)),
        ]
        for title, summary, cat, tags, featured, published in articles:
            article, created = NewsArticle.objects.get_or_create(
                title=title,
                defaults={
                    "summary": summary,
                    "content": f"<p>{summary}</p><p>للاستفسار تواصل مع الاستقبال على تليفون المركز أو عبر واتساب. نلتقي هناك!</p>",
                    "category": cat,
                    "status": NewsArticle.Status.PUBLISHED,
                    "published_at": published,
                    "is_featured": featured,
                    "author": author,
                },
            )
            if created:
                article.tags.set(tags)

        # --- Events
        events = [
            ("بطولة الربيع لكرة القدم الخماسية", "بطولة مفتوحة للفئات العمرية 10-14 سنة — 16 فريقًا، كؤوس ودروع وجوائز.", now + timedelta(days=6), "الملعب الخماسي", 32, True, 0),
            ("يوم مفتوح في حمام السباحة", "دخول مجاني لكل الأعضاء وأسرهم مع ألعاب مائية وجلسات سباحة بإشراف المدربين.", now + timedelta(days=3), "حمام السباحة 25م", 100, True, 0),
            ("رحلة العين السخنة للبراعم", "يوم ترفيهي على الشاطئ للبراعم 8-14 سنة — مواصلات ذهاب وعودة + غداء + تأمين.", now + timedelta(days=14), "نقطة التجمع: بوابة المركز", 40, False, 250),
        ]
        for title, desc, start, location, capacity, is_free, price in events:
            Event.objects.get_or_create(
                title=title,
                defaults={
                    "description": desc,
                    "start_at": start,
                    "location": location,
                    "capacity": capacity,
                    "is_free": is_free,
                    "price": price,
                    "status": Event.Status.PUBLISHED,
                    "created_by": author,
                },
            )

        # --- Gallery
        album, _created = GalleryAlbum.objects.get_or_create(
            title_ar="بطولة الجمهورية للسباحة 2025",
            defaults={"title_en": "Republic Swimming Championship 2025", "description": "لحظات التتويج والإنجاز على مستوى الجمهورية"},
        )
        MediaItem.objects.get_or_create(
            album=album,
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            defaults={"caption": "فيديو تتويج فريق السباحة", "order": 1},
        )

        # --- Facilities
        facilities = [
            ("ملعب كرة القدم الخماسي", "عشب صناعي نجيل عالي الجودة مع كشافات ورشاشات أمان", "ball", "٨ ص – ١٠ م"),
            ("حمام السباحة 25م", "6 حارات + عمق متدرج + سباحة بإشراف مدربين معتمدين", "swim", "٧ ص – ٩ م"),
            ("صالة الجيم", "أجهزة حديثة + إشراف مدرب لياقة", "dumbbell", "٦ ص – ١٠ م"),
            ("صالة تنس الطاولة", "6 طاولات + عشوية + بطولات شهرية", "table", "٩ ص – ١٠ م"),
            ("صالة الكاراتيه والجمباز", "حصير متخصص + بارات جمباز + تدريبات وفِرق تمثيلية", "trophy", "٢ م – ٩ م"),
            ("ملاعب السلة والطائرة", "ملعبان مفتوحان بنجيلة صناعية وقواعد أمان", "ball", "٨ ص – ١٠ م"),
        ]
        for order, (name, desc, icon, hours) in enumerate(facilities):
            Facility.objects.get_or_create(name_ar=name, defaults={"description": desc, "icon": icon, "hours": hours, "order": order})

        # --- Board members
        board = [
            ("اللواء / كمال عبد الجليل", "رئيس مجلس الإدارة"),
            ("أ. / سامي النجار", "نائب رئيس مجلس الإدارة لشئون الرياضة"),
            ("أ. / ميرفت صلاح", "أمين الصندوق"),
            ("أ. / هاني الدسوقي", "أمين السر العام"),
            ("أ. / داليا فؤاد", "مسئولة شئون البراعم والناشئين"),
        ]
        for order, (name, role) in enumerate(board):
            BoardMember.objects.get_or_create(name_ar=name, defaults={"role_ar": role, "order": order})

        # --- FAQs
        faqs = [
            ("إزاي أسجل ابني في المركز؟", "سجل حساب على الموقع برقم موبايلك، ضيف ابنك من صفحة «حسابي ← أبنائي»، وبعدين اختار النشاط أو الدورة المناسبة وادفع رسوم الاشتراك من الاستقبال أو أونلاين."),
            ("الأعمار المتاحة للتسجيل؟", "من 4 سنوات في الجمباز والكاراتيه، و6 سنوات في كرة القدم وباقي الألعاب. الكبار لهم دوري هواة وسباحة."),
            ("مواعيد التجديد السنوي؟", "التجديد يبدأ من أول سبتمبر حتى نهاية أكتوبر بخصم مبكر — بعدها السعر العادي وبدون الخصم."),
            ("هل في رحلات مدرسية أو معسكرات؟", "نعم، معسكرات صيفية لمدة أسبوع في يوليو وأغسطس — تفاصيلها تُعلن قبلها بشهر على الأقل."),
            ("إزاي أتابع حضور ابني في الدورة؟", "من صفحة «حسابي» ستجد نسبة الحضور لكل دورة بعد تفعيل خاصية الحضور في المرحلة القادمة."),
            ("هل في تأمين طبي؟", "كل أعضاء المركز مؤمَّنون ضد الإصابات أثناء التدريبات والمباريات داخل المركز."),
        ]
        for order, (q, a) in enumerate(faqs):
            FAQ.objects.get_or_create(question_ar=q, defaults={"answer_ar": a, "order": order})

        self.stdout.write(self.style.SUCCESS("Content OK - أخبار، أنشطة، معرض، مرافق، مجلس إدارة، أسئلة شائعة"))

    def _seed_memberships(self, user, profile, dependent):
        """نوع اشتراك فردي + كوبونات + اشتراك منتهي للديمو (ليظهر التجديد)."""
        today = timezone.now().date()
        mtype, _created = MembershipType.objects.get_or_create(
            name_ar="الاشتراك الفردي السنوي",
            defaults={
                "name_en": "Individual Annual Membership",
                "description": "12 شهرًا — كل الملاعب والصالات والبطولات بأسعار مخفضة",
                "price": 25,
                "duration_months": 12,
                "is_active": True,
                "order": 0,
            },
        )
        Coupon.objects.get_or_create(code="AHLAN2026", defaults={"kind": Coupon.Kind.PERCENT, "value": 10, "valid_from": today - timedelta(days=30), "valid_to": today + timedelta(days=180), "is_active": True})
        Coupon.objects.get_or_create(code="STUDENT20", defaults={"kind": Coupon.Kind.PERCENT, "value": 20, "valid_from": today - timedelta(days=30), "valid_to": today + timedelta(days=180), "usage_limit": 500, "is_active": True})
        # هجرة القيمة القديمة 1200 → 25 (فقط لو لسه زي ما هي)
        MembershipType.objects.filter(name_ar="الاشتراك الفردي السنوي", price=1200).update(price=25)
        Coupon.objects.get_or_create(code="FIXED100", defaults={"kind": Coupon.Kind.FIXED, "value": 100, "valid_from": today - timedelta(days=30), "valid_to": today + timedelta(days=180), "is_active": True})

        # اشتراك منتهي لمستخدم الديمو — يبرز شاشة «جدّد اشتراكك»
        start = today - timedelta(days=380)
        end = today - timedelta(days=16)
        Membership.objects.get_or_create(
            member=user, for_user=user, membership_type=mtype,
            defaults={
                "start_date": start, "end_date": end, "status": Membership.Status.EXPIRED,
                "base_amount": mtype.price, "discount_amount": 0, "total_amount": mtype.price,
            },
        )
        # اشتراك نشط للتابع يوسف
        Membership.objects.get_or_create(
            member=user, for_dependent=dependent, membership_type=mtype,
            defaults={
                "start_date": today - timedelta(days=180), "end_date": today + timedelta(days=185),
                "status": Membership.Status.ACTIVE, "base_amount": mtype.price,
                "discount_amount": 0, "total_amount": mtype.price,
            },
        )
        self.stdout.write(self.style.SUCCESS("Memberships OK - نوع + كوبونات + سجل ديمو"))

    def _seed_tournaments(self, demo_user, demo_dependent):
        """9 رياضات + بطولة تجريبية U14 خماسية بجداول وترتيب (للعرض الفوري)."""
        from decimal import Decimal

        from apps.tournaments.models import Match, MatchGoal, Sport, Standing, Team, TeamMember, Tournament, TournamentCategory, TournamentRegistration
        from apps.tournaments.services import ensure_standings, generate_round_robin, recompute_standings

        sports = [
            ("كرة القدم", "Football", "ball", True, 1), ("كرة السلة", "Basketball", "ball", True, 2),
            ("كرة الطائرة", "Volleyball", "ball", True, 3), ("كرة اليد", "Handball", "ball", True, 4),
            ("تنس الطاولة", "Table Tennis", "table", False, 5), ("السباحة", "Swimming", "swim", False, 6),
            ("الكاراتيه", "Karate", "trophy", False, 7), ("الجمباز", "Gymnastics", "trophy", False, 8),
            ("ألعاب القوى", "Athletics", "trophy", False, 9),
        ]
        sport_objs = {}
        for ar, en, icon, is_team, order in sports:
            s, _created = Sport.objects.get_or_create(name_ar=ar, defaults={"name_en": en, "icon": icon, "is_team_sport": is_team, "order": order})
            sport_objs[ar] = s

        now = timezone.now()
        tournament, created = Tournament.objects.get_or_create(
            name="بطولة الربيع لكرة القدم الخماسية — تحت 14 سنة",
            defaults={
                "sport": sport_objs["كرة القدم"],
                "description": "بطولة مفتوحة للبراعم والناشئين تحت 14 سنة — بطولة الربيع السنوية للمركز بمشاركة فرق من مراكز دمياط. نظمها: اتحاد كرة القدم المصري + المركز. الرسوم مجانية والجوائز لكل مركز.",
                "registration_type": Tournament.RegistrationType.TEAM,
                "format": Tournament.Format.LEAGUE,
                "max_teams": 8,
                "squad_size": 12,
                "entry_fee": Decimal("0"),
                "status": Tournament.Status.REGISTRATION,
                "registration_start": (now - timezone.timedelta(days=14)).date(),
                "registration_end": (now + timezone.timedelta(days=30)).date(),
                "start_date": (now + timezone.timedelta(days=35)).date(),
                "end_date": (now + timezone.timedelta(days=50)).date(),
                "prizes": "كؤوس + دروع + ميداليات لكل اللاعبين + مكافأة مالية للبطل",
                "sponsors": "المركز — محافظة دمياط — شركة المحمود للكيماويات",
            },
        )
        category, _created = TournamentCategory.objects.get_or_create(
            tournament=tournament,
            name_ar="الفئة العمرية تحت 14 سنة",
            defaults={"name_en": "U14", "gender": TournamentCategory.Gender.MALE, "age_min": 10, "age_max": 14, "entry_fee": None},
        )

        # كباتن الفرق التجريبية
        User = get_user_model()
        captains = {}
        for idx, (phone, name) in enumerate([("02000000001", "إسلام الفرماوي"), ("02000000002", "كريم شوقي"), ("02000000003", "مصطفى السعيد")]):
            cap, created_cap = User.objects.get_or_create(phone=phone, defaults={"username": phone, "first_name": name.split()[0], "last_name": name.split()[1], "is_active": True})
            if created_cap:
                cap.set_password("Demo@12345")
                cap.save(update_fields=["password"])
            captains[phone] = cap

        team_specs = [
            ("نجوم الحوراني", demo_user),
            ("شبان فارسكور", captains["02000000001"]),
            ("براعم النيل", captains["02000000002"]),
            ("أكاديمية الدمياط", captains["02000000003"]),
        ]
        teams = []
        for name, captain in team_specs:
            team, _created = Team.objects.get_or_create(tournament=tournament, category=category, name=name, defaults={"captain": captain, "coach_name": "الكابتن " + captain.first_name})
            teams.append(team)
            TeamMember.objects.get_or_create(team=team, player=captain)
        TeamMember.objects.get_or_create(team=teams[0], dependent=demo_dependent)

        # تسجيل أحمد مقبول (عرض «تسجيلك مقبول»)
        TournamentRegistration.objects.get_or_create(
            tournament=tournament, category=category, registered_by=demo_user, kind="team",
            defaults={"team": teams[0], "status": TournamentRegistration.Status.ACCEPTED, "fee_amount": 0},
        )

        # توليد الجدول + نتائج مباراتين ليرتسم الترتيب فورًا
        ensure_standings(category)
        if not Match.objects.filter(category=category).exists():
            fixtures = generate_round_robin(category)
            evening = now.replace(hour=18, minute=0, second=0)
            for i, m in enumerate(fixtures):
                m.scheduled_at = evening + timezone.timedelta(days=i + 1)
                m.venue = "الملعب الخماسي" if i % 2 == 0 else "ملعب السلة"
                m.save(update_fields=["scheduled_at", "venue"])
                if i == 0:
                    m.team_a, m.team_b = teams[0], teams[1]
                    m.score_a, m.score_b, m.status = 3, 1, Match.Status.FINISHED
                    m.save(update_fields=["team_a", "team_b", "score_a", "score_b", "status", "updated_at"])
                    MatchGoal.objects.create(match=m, team=teams[0], scorer_name="يوسف أحمد الحوراني", minute=12)
                    MatchGoal.objects.create(match=m, team=teams[0], scorer_name="يوسف أحمد الحوراني", minute=34)
                    MatchGoal.objects.create(match=m, team=teams[0], scorer=demo_user, minute=78)
                    MatchGoal.objects.create(match=m, team=teams[1], scorer_name="محمود علي", minute=55)
                elif i == 1:
                    m.team_a, m.team_b = teams[2], teams[3]
                    m.score_a, m.score_b, m.status = 1, 1, Match.Status.FINISHED
                    m.save(update_fields=["team_a", "team_b", "score_a", "score_b", "status", "updated_at"])
                    MatchGoal.objects.create(match=m, team=teams[2], scorer_name="عمر ياسر", minute=21)
                    MatchGoal.objects.create(match=m, team=teams[3], scorer_name="زياد حامد", minute=67)
        recompute_standings(category)
        self.stdout.write(self.style.SUCCESS("Tournaments OK - 9 رياضات + بطولة U14 خماسية + جدول وترتيب"))

    def _seed_courses(self, demo_user, demo_dependent):
        """3 دورات تجريبية + يوسف في الكاراتيه مع سجل حضور (للعرض الفوري)."""
        from decimal import Decimal

        from apps.courses.models import Attendance, Course, CourseEnrollment
        from apps.tournaments.models import Sport

        User = get_user_model()
        coach, _created = User.objects.get_or_create(phone="02000000004", defaults={"username": "02000000004", "first_name": "تامر", "last_name": "فؤاد", "is_active": True})
        if not coach.has_usable_password():
            coach.set_password("Demo@12345")
            coach.save(update_fields=["password"])

        karate = Sport.objects.get(name_ar="الكاراتيه")
        swimming = Sport.objects.get(name_ar="السباحة")
        table_tennis = Sport.objects.get(name_ar="تنس الطاولة")

        now = timezone.now()
        specs = [
            ("كاراتيه للبراعم — القيادة والانضباط", karate, Course.Level.BEGINNER, Course.Gender.MALE, 6, 12, "السبت والاثنين ٥:٠٠ – ٦:٠٠ مساءً", "صالة الجمباز", 150, 8, 15, True, Course.Status.OPEN),
            ("سباحة للمبتدئين — تأهيل ٢٠٢٦", swimming, Course.Level.BEGINNER, Course.Gender.MIXED, 6, 14, "الأحد والثلاثاء ٤:٠٠ – ٥:٠٠ مساءً", "حمام السباحة 25م", 200, 12, 12, True, Course.Status.OPEN),
            ("تنس طاولة — دوري الأبطال للهواة", table_tennis, Course.Level.ALL, Course.Gender.MIXED, 12, 99, "الأربعاء والسبت ٧:٠٠ – ٩:٠٠ مساءً", "صالة تنس الطاولة", 100, 10, 10, False, Course.Status.OPEN),
        ]
        courses = {}
        for name, sport, level, gender, age_min, age_max, schedule, location, price, weeks, capacity, medical, status in specs:
            course, _created = Course.objects.get_or_create(
                name=name,
                defaults={
                    "sport": sport, "level": level, "gender": gender, "age_min": age_min, "age_max": age_max,
                    "schedule": schedule, "location": location, "price": Decimal(str(price)),
                    "price_type": Course.PriceType.MONTHLY, "capacity": capacity, "duration_weeks": weeks,
                    "requires_medical": medical, "status": status, "coach": coach,
                    "start_date": (now - timezone.timedelta(days=21)).date(),
                    "description": "برنامج تدريبي معتمد ينمّي المهارات البدنية والنفسية بإشراف مدرب معتمد من المركز.",
                },
            )
            courses[name] = course

        # يوسف في كاراتيه مع حضور ٣ جلسات
        karate_course = courses["كاراتيه للبراعم — القيادة والانضباط"]
        enrollment, _created = CourseEnrollment.objects.get_or_create(
            course=karate_course, for_dependent=demo_dependent,
            defaults={"member": demo_user, "status": CourseEnrollment.Status.CONFIRMED, "fee_amount": Decimal("150"), "health_acknowledged": True},
        )
        today = timezone.now().date()
        present_count = 0
        for i in range(3):
            session_date = today - timedelta(days=7 * (i + 1))
            att, _created = Attendance.objects.get_or_create(
                enrollment=enrollment, session_date=session_date,
                defaults={"present": i != 1, "marked_by": coach},
            )
            present_count += int(att.present)
        self.stdout.write(self.style.SUCCESS(f"Courses OK - 3 دورات + يوسف في كاراتيه بحضور {present_count}/3"))

    def _seed_trips(self, demo_user, demo_dependent):
        """رحلة ديمو: العين السخنة للبراعم + حجز مؤكد للديمو (أحمد ويوسف)."""
        from decimal import Decimal

        from apps.trips.models import GuardianConsent, Trip, TripBooking, TripPassenger

        now = timezone.now()
        trip, _created = Trip.objects.get_or_create(
            name="رحلة العين السخنة للبراعم",
            defaults={
                "destination": "العين السخنة — شرم السويس",
                "description": "رحلة ترفيهية يوم كامل: شاطئ خاص + ألعاب مائية + أنشطة جماعية + وجبتان + تأمين صحي + مواصلات ذهاب وعودة من باب المركز. للبراعم 8-14 سنة بإشراف مدربي المركز.",
                "trip_date": (now + timezone.timedelta(days=21)).date(),
                "meeting_point": "بوابة المركز",
                "meeting_time": timezone.datetime.strptime("07:30", "%H:%M").time().replace(tzinfo=None),
                "member_price": Decimal("250"),
                "guest_price": Decimal("300"),
                "capacity": 40,
                "min_age": 8,
                "max_age": 14,
                "supervisors": "الكابتن تامر (كاراتيه) · الكابتن إسلام · الإدارية م/ ميرفت",
                "rules": "ممنوع المأكولات من الخارج · الالتزام بالعودة الساعة 6 مساءً · التأمين الصحي إجباري للأطفال · الطاعة للمشرفين طوال الرحلة.",
                "status": Trip.Status.OPEN,
            },
        )

        booking, created = TripBooking.objects.get_or_create(
            trip=trip, booked_by=demo_user,
            defaults={
                "passengers_count": 2, "member_count": 2, "guest_count": 0,
                "total_amount": Decimal("500"), "status": TripBooking.Status.CONFIRMED,
                "note": "حساسية من المكسرات — رحلة يوسف",
            },
        )
        if created:
            p_self = TripPassenger.objects.create(booking=booking, relation=TripPassenger.Relation.SELF, full_name="أحمد محمود الحوراني", age=38, medical_notes="")
            p_dep = TripPassenger.objects.create(booking=booking, relation=TripPassenger.Relation.DEPENDENT, full_name="يوسف أحمد الحوراني", age=9, medical_notes="حساسية من المكسرات")
            GuardianConsent.objects.create(
                passenger=p_dep, booking=booking, guardian=demo_user,
                signature_name="أحمد محمود الحوراني", consent_text=GuardianConsent.CONSENT_TEXT,
                ip_address="127.0.0.1",
            )
        self.stdout.write(self.style.SUCCESS(f"Trips OK - رحلة العين السخنة + حجز {booking.reference} (أحمد + يوسف)"))

    def _seed_notification_templates(self):
        """قوالب الإشعارات العربية — قابلة للتعديل من لوحة التحكم بعد ذلك."""
        from apps.notifications.models import NotificationTemplate

        templates = [
            ("welcome", "أهلاً بيك في مركز شباب الحوراني! 🎉", "أهلاً {name}، تم إنشاء عضويتك برقم {ref}. نتشرف بوجودك في أنشطة المركز — بطولات، دورات، رحلات وأنشطة ترفيهية لكل الأعمار."),
            ("renewal_30", "اشتراكك على مشارف الانتهاء — باقي {days} يوم", "أهلاً {name}، اشتراك {type} ينتهي في {end_date} ({days} يومًا). جدد بضغطة زر من موبايلك من صفحة «تجديد الاشتراك»."),
            ("renewal_7", "باقي أسبوع لاشتراكك — جدد الآن", "أهلاً {name}، باقي {days} أيام على انتهاء اشتراك {type} ({end_date}). التجديد في 3 خطوات وعبر Paymob أو المحفظة أو الدفع نقدًا بالمركز."),
            ("renewal_1", "آخر يوم في اشتراكك!", "أهلاً {name}، بكرة {end_date} ينتهي اشتراك {type}. لديك فترة سماح 7 أيام — جدد الآن لتتجنب غرامة التأخير."),
            ("payment_confirmed", "تم تأكيد دفعتك", "شكراً {name}! تم تأكيد دفعتك بنجاح. (المبلغ: {amount} ج — المرجع: {ref}). الفاتورة متاحة الآن في «مدفوعاتي»."),
            ("payment_received", "استلمنا إيصالك — قيد المراجعة", "أهلاً {name}، استلمنا إيصال التحويل رقم {ref} بمبلغ {amount} ج. سيراجعه موظف المركز ويفعّل اشتراكك خلال ساعات العمل."),
        ]
        for code, subject, body in templates:
            NotificationTemplate.objects.get_or_create(code=code, defaults={"subject_ar": subject, "body_ar": body})
        self.stdout.write(self.style.SUCCESS("Notification templates OK"))
