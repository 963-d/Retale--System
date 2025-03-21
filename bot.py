import os
import discord
from discord import app_commands
from discord.ext import tasks
from discord.ui import Button, View, Modal, TextInput
from dotenv import load_dotenv
import json
import asyncio
from notifications import NotificationManager
import datetime
import io

# تحميل المتغيرات البيئية
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# إعداد البوت
class YouTubeBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)
        self.settings = {}
        self.SETTINGS_FILE = 'settings.json'
        self.notification_manager = None
        self.ticket_counter = 0

    async def setup_hook(self):
        await self.tree.sync()

client = YouTubeBot()

# تحميل الإعدادات
def load_settings():
    try:
        with open(client.SETTINGS_FILE, 'r', encoding='utf-8') as f:
            client.settings = json.load(f)
            # تحميل رقم آخر تذكرة
            client.ticket_counter = client.settings.get('last_ticket_number', 0)
    except FileNotFoundError:
        client.settings = {
            'youtube_channels': {},
            'notification_channels': {},
            'verification_roles': {},
            'verification_messages': {},
            'ticket_category': None,
            'last_ticket_number': 0,
            'support_role': None,
            'logs_channel': None
        }
        save_settings()

# حفظ الإعدادات
def save_settings():
    with open(client.SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(client.settings, f, indent=4)

@client.event
async def on_ready():
    print(f'{client.user} تم تشغيل البوت بنجاح!')
    load_settings()
    client.notification_manager = NotificationManager()
    check_youtube_updates.start()

@client.event
async def on_message(message):
    # تجاهل رسائل البوت
    if message.author.bot:
        return

    # التحقق من الصلاحيات
    if not message.author.guild_permissions.manage_messages:
        return

    # مسح الرسائل عند كتابة "م"
    if message.content == 'م':
        try:
            # مسح جميع الرسائل في القناة
            await message.channel.purge(limit=None)
            # إرسال رسالة تأكيد
            confirm_msg = await message.channel.send('💙 تم مسح جميع الرسائل!')
            # حذف رسالة التأكيد بعد 3 ثواني
            await asyncio.sleep(0.5)
            await confirm_msg.delete()
        except discord.Forbidden:
            await message.channel.send('❌ ليس لدي صلاحية حذف الرسائل!')
        except Exception as e:
            await message.channel.send(f'❌ حدث خطأ: {str(e)}')

    # مسح عدد محدد من الرسائل
    elif message.content.startswith('م '):
        try:
            # الحصول على العدد من الرسالة
            number = int(message.content.split()[1])
            # مسح العدد المحدد من الرسائل + رسالة الأمر نفسها
            deleted = await message.channel.purge(limit=number + 1)
            # إرسال رسالة تأكيد
            confirm_msg = await message.channel.send(f'💙 تم مسح {len(deleted)-1} رسالة!')
            # حذف رسالة التأكيد بعد 3 ثواني
            await asyncio.sleep(0.5)
            await confirm_msg.delete()
        except ValueError:
            await message.channel.send('❌ الرجاء إدخال رقم صحيح!')
        except discord.Forbidden:
            await message.channel.send('❌ ليس لدي صلاحية حذف الرسائل!')
        except Exception as e:
            await message.channel.send(f'❌ حدث خطأ: {str(e)}')

    # التحقق من أوامر التذاكر
    if isinstance(message.channel, discord.TextChannel) and message.channel.name.startswith("تذكرة-"):
        if message.content.lower() == "close#":
            # حفظ المحادثة
            transcript = []
            async for msg in message.channel.history(limit=None, oldest_first=True):
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                transcript.append(f"[{timestamp}] {msg.author.name}: {msg.content}")
            
            # إنشاء ملف المحادثة
            transcript_text = "\n".join(transcript)
            transcript_file = discord.File(
                fp=io.StringIO(transcript_text),
                filename=f"transcript-{message.channel.name}.txt"
            )
            
            # إرسال نسخة من المحادثة للعضو
            try:
                embed = discord.Embed(
                    title="📝 سجل المحادثة",
                    description=f"تم إغلاق التذكرة {message.channel.name}",
                    color=discord.Color.blue()
                )
                await message.author.send(embed=embed, file=transcript_file)
            except:
                pass
            
            # إغلاق التذكرة
            await message.channel.send("🔒 جاري إغلاق التذكرة...")
            await asyncio.sleep(5)
            await message.channel.delete()

@client.event
async def on_raw_reaction_add(payload):
    # تجاهل تفاعلات البوت
    if payload.user_id == client.user.id:
        return

    guild = client.get_guild(payload.guild_id)
    if not guild:
        return

    # التحقق من رسائل التحقق
    if str(payload.message_id) in client.settings.get('verification_messages', {}):
        if str(payload.emoji) == "💙":  # تغيير الإيموجي إلى 💙
            role_id = client.settings['verification_roles'].get(str(guild.id))
            if role_id:
                role = guild.get_role(int(role_id))
                if role:
                    member = guild.get_member(payload.user_id)
                    if member:
                        try:
                            await member.add_roles(role)
                            # إرسال رسالة ترحيب في الخاص
                            try:
                                embed = discord.Embed(
                                    title="💙 أهلاً وسهلاً بك!",
                                    description=f"نرحب بك في مجتمع {guild.name} 💙",
                                    color=discord.Color.blue()
                                )
                                
                                embed.add_field(
                                    name="💙 تم التحقق بنجاح",
                                    value=f"تم منحك رتبة `{role.name}`",
                                    inline=False
                                )
                                
                                embed.add_field(
                                    name="💙 القوانين",
                                    value="• احترام جميع الأعضاء\n"
                                          "• عدم نشر المحتوى المخالف\n"
                                          "• الالتزام بقوانين السيرفر",
                                    inline=False
                                )
                                
                                embed.add_field(
                                    name="💙 مميزات العضوية",
                                    value="• الوصول إلى جميع القنوات\n"
                                          "• المشاركة في المحادثات\n"
                                          "• حضور الفعاليات الخاصة",
                                    inline=False
                                )
                                
                                embed.set_footer(text="نتمنى لك وقتاً ممتعاً! 🌟")
                                await member.send(embed=embed)
                            except:
                                pass  # تجاهل إذا كانت الرسائل الخاصة مقفلة
                        except discord.Forbidden:
                            print(f"لا يمكن إضافة الرتبة للعضو {member.name}")

    # التحقق من رسائل التذاكر
    channel = guild.get_channel(payload.channel_id)
    if channel and channel.name == "إنشاء-تذكرة" and str(payload.emoji) == "📩":
        member = guild.get_member(payload.user_id)
        
        # زيادة عداد التذاكر
        client.ticket_counter += 1
        client.settings['last_ticket_number'] = client.ticket_counter
        save_settings()
        
        # إنشاء قناة التذكرة
        ticket_channel = await guild.create_text_channel(
            f"تذكرة-{client.ticket_counter}",
            category=guild.get_channel(client.settings['ticket_category'])
        )
        
        # إعداد صلاحيات القناة
        await ticket_channel.set_permissions(guild.default_role, read_messages=False)
        await ticket_channel.set_permissions(member, read_messages=True, send_messages=True)
        support_role = guild.get_role(client.settings['support_role'])
        if support_role:
            await ticket_channel.set_permissions(support_role, read_messages=True, send_messages=True)
        
        # إرسال رسالة الترحيب
        embed = discord.Embed(
            title=f"تذكرة #{client.ticket_counter}",
            description=f"مرحباً {member.mention}!\nسيقوم فريق الدعم الفني بالرد عليك قريباً.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(
            name="تعليمات",
            value="• اشرح مشكلتك بالتفصيل\n"
                  "• انتظر رد فريق الدعم\n"
                  "• لإغلاق التذكرة اكتب `close#`",
            inline=False
        )
        await ticket_channel.send(f"{member.mention} {support_role.mention}", embed=embed)

@client.tree.command(name="setup_verification", description="إعداد نظام التحقق")
@app_commands.default_permissions(administrator=True)
async def setup_verification(interaction: discord.Interaction):
    try:
        # التحقق من صلاحيات البوت
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ ليس لدي صلاحية إدارة الرتب!", ephemeral=True)
            return

        # البحث عن الرتبة المطلوبة
        role = discord.utils.get(interaction.guild.roles, name="𝐌𝐄𝐌𝐁𝐄𝐑𝐒 💙")
        if not role:
            # إنشاء الرتبة إذا لم تكن موجودة
            try:
                role = await interaction.guild.create_role(name="𝐌𝐄𝐌𝐁𝐄𝐑𝐒 💙", color=discord.Color.blue())
                await interaction.response.send_message("💙 تم إنشاء الرتبة بنجاح!", ephemeral=True)
            except:
                await interaction.response.send_message("❌ فشل في إنشاء الرتبة!", ephemeral=True)
                return
            
        # التحقق من ترتيب الرتب
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("❌ يجب أن تكون رتبة البوت أعلى من رتبة 𝐌𝐄𝐌𝐁𝐄𝐑𝐒 💙!", ephemeral=True)
            return

        # إنشاء روم التحقق
        verify_channel = await interaction.guild.create_text_channel("💙〢𝐕𝐞𝐫𝐢𝐟𝐲")
        
        # إخفاء جميع الرومات عن everyone وإظهارها فقط لرتبة MEMBERS
        for channel in interaction.guild.channels:
            if channel.id != verify_channel.id:  # تجاهل روم التحقق
                await channel.set_permissions(interaction.guild.default_role, view_channel=False)
                await channel.set_permissions(role, view_channel=True)
        
        # إعداد صلاحيات روم التحقق
        await verify_channel.set_permissions(interaction.guild.default_role, view_channel=True, send_messages=False)
        await verify_channel.set_permissions(role, view_channel=False)  # إخفاء روم التحقق عن الأعضاء المتحققين

        guild_id = str(interaction.guild_id)
        
        # حفظ معرف الرتبة
        if 'verification_roles' not in client.settings:
            client.settings['verification_roles'] = {}
        client.settings['verification_roles'][guild_id] = role.id
        
        # إنشاء رسالة التحقق
        embed = discord.Embed(
            title="🔒 نظام التحقق",
            description="اضغط على 💙 للحصول على رتبة 𝐌𝐄𝐌𝐁𝐄𝐑𝐒 💙 ورؤية باقي الرومات",
            color=discord.Color.blue()
        )
        
        try:
            message = await verify_channel.send(embed=embed)
            await message.add_reaction("💙")
            
            # حفظ معرف الرسالة للتحقق لاحقاً
            if 'verification_messages' not in client.settings:
                client.settings['verification_messages'] = {}
            client.settings['verification_messages'][str(message.id)] = True
            
            save_settings()
            await interaction.response.send_message("💙 تم إعداد نظام التحقق بنجاح!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ ليس لدي صلاحية إرسال رسائل أو إضافة تفاعلات في هذه القناة!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ غير متوقع: {str(e)}", ephemeral=True)

@client.tree.command(name="addchannel", description="إضافة قناة يوتيوب للمتابعة")
async def add_youtube_channel(interaction: discord.Interaction, channel_id: str):
    guild_id = str(interaction.guild_id)
    if not client.settings['youtube_channels'].get(guild_id):
        client.settings['youtube_channels'][guild_id] = []
    
    if channel_id not in client.settings['youtube_channels'][guild_id]:
        client.settings['youtube_channels'][guild_id].append(channel_id)
        client.settings['notification_channels'][guild_id] = interaction.channel_id
        save_settings()
        await interaction.response.send_message(f'💙 تم إضافة قناة اليوتيوب بنجاح! سيتم إرسال الإشعارات في هذه القناة.')
    else:
        await interaction.response.send_message('⚠️ هذه القناة مضافة مسبقاً!')

@client.tree.command(name="removechannel", description="إزالة قناة يوتيوب من المتابعة")
async def remove_youtube_channel(interaction: discord.Interaction, channel_id: str):
    guild_id = str(interaction.guild_id)
    if client.settings['youtube_channels'].get(guild_id):
        if channel_id in client.settings['youtube_channels'][guild_id]:
            client.settings['youtube_channels'][guild_id].remove(channel_id)
            save_settings()
            await interaction.response.send_message('💙 تم إزالة قناة اليوتيوب بنجاح!')
        else:
            await interaction.response.send_message('⚠️ هذه القناة غير موجودة في القائمة!')

@client.tree.command(name="listchannels", description="عرض قائمة القنوات المتابعة")
async def list_youtube_channels(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    if client.settings['youtube_channels'].get(guild_id):
        channels = client.settings['youtube_channels'][guild_id]
        if channels:
            embed = discord.Embed(
                title='📋 قائمة قنوات اليوتيوب المتابعة',
                description='\n'.join([f'• `{channel}`' for channel in channels]),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message('لا توجد قنوات متابعة حالياً!')
    else:
        await interaction.response.send_message('لا توجد قنوات متابعة حالياً!')

@tasks.loop(minutes=5)
async def check_youtube_updates():
    for guild_id, channels in client.settings['youtube_channels'].items():
        notification_channel_id = client.settings['notification_channels'].get(guild_id)
        if notification_channel_id:
            channel = client.get_channel(int(notification_channel_id))
            if channel:
                for youtube_channel in channels:
                    new_videos = await client.notification_manager.check_youtube_updates(youtube_channel)
                    for video in new_videos:
                        embed = discord.Embed(
                            title=video['title'],
                            url=video['url'],
                            color=discord.Color.red()
                        )
                        embed.set_thumbnail(url=video['thumbnail'])
                        embed.add_field(name='🎥 فيديو جديد!', value='تم نشر فيديو جديد على اليوتيوب!')
                        await channel.send(embed=embed)

@client.tree.command(name="help", description="عرض قائمة الأوامر المتاحة")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title='📚 دليل الأوامر',
        description='قائمة بجميع الأوامر المتاحة:',
        color=discord.Color.red()
    )
    embed.add_field(name='/addchannel [معرف_القناة]', value='إضافة قناة يوتيوب للمتابعة', inline=False)
    embed.add_field(name='/removechannel [معرف_القناة]', value='إزالة قناة يوتيوب من المتابعة', inline=False)
    embed.add_field(name='/listchannels', value='عرض قائمة القنوات المتابعة', inline=False)
    embed.add_field(name='/setup_verification', value='إعداد نظام التحقق (للإدارة فقط)', inline=False)
    embed.add_field(name='/help', value='عرض هذه القائمة', inline=False)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="setup_tickets", description="إعداد نظام التذاكر")
@app_commands.default_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    try:
        # إنشاء رتبة الدعم الفني إذا لم تكن موجودة
        support_role = discord.utils.get(interaction.guild.roles, name="الدعم الفني")
        if not support_role:
            support_role = await interaction.guild.create_role(
                name="الدعم الفني",
                color=discord.Color.blue(),
                mentionable=True
            )
        
        # إنشاء فئة التذاكر إذا لم تكن موجودة
        category = discord.utils.get(interaction.guild.categories, name="〢 Ticket")
        if not category:
            category = await interaction.guild.create_category("〢 Ticket")
        
        # حفظ معرفات الفئة والرتبة
        client.settings['ticket_category'] = category.id
        client.settings['support_role'] = support_role.id
        save_settings()
        
        # إنشاء قناة الدعم الفني
        channel = await interaction.guild.create_text_channel(
            '🎫〢الدعــم・الفــنــي',
            category=category
        )

        # إعداد صلاحيات القناة
        await channel.set_permissions(interaction.guild.default_role, view_channel=True, send_messages=False)
        await channel.set_permissions(support_role, view_channel=True, send_messages=True)

        # إنشاء زر إنشاء التذكرة
        create_button = Button(style=discord.ButtonStyle.primary, label="إنشاء تذكرة", emoji="📩", custom_id="create_ticket")
        
        async def create_button_callback(button_interaction):
            if button_interaction.user == button_interaction.message.author:
                return
            
            modal = TicketModal()
            await button_interaction.response.send_modal(modal)
        
        create_button.callback = create_button_callback
        view = View(timeout=None)  # جعل الزر دائم
        view.add_item(create_button)
        
        # إنشاء رسالة إنشاء التذكرة
        embed = discord.Embed(
            title="🎫 مركز المساعدة والدعم الفني",
            description="مرحباً بك في مركز المساعدة! للحصول على المساعدة، اضغط على الزر أدناه لإنشاء تذكرة",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📋 التعليمات",
            value="• يرجى كتابة سبب فتح التذكرة بوضوح\n"
                  "• كن صبوراً، سيتم الرد عليك من قبل فريق الدعم\n"
                  "• يمكنك إغلاق التذكرة بالضغط على زر الإغلاق",
            inline=False
        )
        embed.add_field(
            name="⚠️ ملاحظة",
            value="• يرجى عدم إنشاء تذاكر متكررة\n"
                  "• سيتم تجاهل التذاكر الغير مهمة\n"
                  "• احترام قوانين السيرفر في التذاكر",
            inline=False
        )
        
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ تم إعداد نظام التذاكر بنجاح!", ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {str(e)}", ephemeral=True)

class TicketModal(Modal, title="إنشاء تذكرة جديدة"):
    reason = TextInput(
        label="سبب فتح التذكرة",
        placeholder="اكتب سبب فتح التذكرة هنا...",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=10,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        # زيادة عداد التذاكر
        client.ticket_counter += 1
        client.settings['last_ticket_number'] = client.ticket_counter
        save_settings()
        
        # إنشاء قناة التذكرة في الكاتيجوري المحدد
        category = discord.utils.get(interaction.guild.categories, name="〢 Ticket")
        if not category:
            category = await interaction.guild.create_category("〢 Ticket")
        
        # إنشاء قناة التذكرة
        ticket_channel = await interaction.guild.create_text_channel(
            f"ticket-{client.ticket_counter}",
            category=category
        )
        
        # إعداد صلاحيات القناة
        await ticket_channel.set_permissions(interaction.guild.default_role, read_messages=False)
        await ticket_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        support_role = interaction.guild.get_role(client.settings['support_role'])
        if support_role:
            await ticket_channel.set_permissions(support_role, read_messages=True, send_messages=True)
        
        # إنشاء زر إغلاق التذكرة
        close_button = Button(style=discord.ButtonStyle.danger, label="إغلاق التذكرة", emoji="🔒", custom_id="close_ticket")
        
        async def close_button_callback(button_interaction):
            if button_interaction.user == interaction.user or support_role in button_interaction.user.roles:
                # حفظ المحادثة
                transcript = []
                async for msg in ticket_channel.history(limit=None, oldest_first=True):
                    timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    transcript.append(f"[{timestamp}] {msg.author.name}: {msg.content}")
                
                # إنشاء ملف المحادثة
                transcript_text = "\n".join(transcript)
                transcript_file = discord.File(
                    fp=io.StringIO(transcript_text),
                    filename=f"transcript-ticket-{client.ticket_counter}.txt"
                )
                
                # إرسال نسخة من المحادثة للعضو
                try:
                    embed = discord.Embed(
                        title="📝 سجل المحادثة",
                        description=f"تم إغلاق التذكرة ticket-{client.ticket_counter}",
                        color=discord.Color.blue()
                    )
                    await interaction.user.send(embed=embed, file=transcript_file)
                except:
                    pass
                
                # إغلاق التذكرة
                await button_interaction.response.send_message("🔒 جاري إغلاق التذكرة...")
                await asyncio.sleep(5)
                await ticket_channel.delete()
        
        close_button.callback = close_button_callback
        view = View(timeout=None)  # جعل الزر دائم
        view.add_item(close_button)
        
        # إرسال رسالة الترحيب
        embed = discord.Embed(
            title=f"تذكرة #{client.ticket_counter}",
            description=f"مرحباً {interaction.user.mention}!\nسيقوم فريق الدعم الفني بالرد عليك قريباً.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(
            name="📝 سبب التذكرة",
            value=self.reason.value,
            inline=False
        )
        embed.add_field(
            name="تعليمات",
            value="• انتظر رد فريق الدعم\n"
                  "• يمكنك إغلاق التذكرة بالضغط على الزر أدناه",
            inline=False
        )
        await ticket_channel.send(f"{interaction.user.mention} {support_role.mention}", embed=embed, view=view)
        await interaction.response.send_message(f"✅ تم إنشاء تذكرتك في القناة {ticket_channel.mention}", ephemeral=True)

@client.tree.command(name="setup_logs", description="إعداد نظام السجلات")
@app_commands.default_permissions(administrator=True)
async def setup_logs(interaction: discord.Interaction):
    try:
        # إنشاء فئة السجلات
        logs_category = discord.utils.get(interaction.guild.categories, name="〢 LOGS")
        if not logs_category:
            logs_category = await interaction.guild.create_category("〢 LOGS")
            
        # إنشاء قناة السجلات
        logs_channel = await interaction.guild.create_text_channel(
            'server-logs',
            category=logs_category
        )
        
        # تعيين صلاحيات القناة
        await logs_channel.set_permissions(interaction.guild.default_role, read_messages=False)
        await logs_channel.set_permissions(interaction.guild.me, read_messages=True, send_messages=True)
        
        # حفظ معرف قناة السجلات
        client.settings['logs_channel'] = logs_channel.id
        save_settings()
        
        await interaction.response.send_message("✅ تم إعداد نظام السجلات بنجاح!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {str(e)}", ephemeral=True)

async def send_log(guild, title, description, color=discord.Color.blue()):
    if not client.settings.get('logs_channel'):
        return
        
    channel = guild.get_channel(client.settings['logs_channel'])
    if channel:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.utcnow()
        )
        await channel.send(embed=embed)

# سجلات الأعضاء
@client.event
async def on_member_join(member):
    await send_log(
        member.guild,
        "👋 عضو جديد",
        f"**الاسم:** {member.mention}\n"
        f"**المعرف:** {member.id}\n"
        f"**تاريخ إنشاء الحساب:** {member.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        discord.Color.green()
    )

@client.event
async def on_member_remove(member):
    await send_log(
        member.guild,
        "🚶‍♂️ مغادرة عضو",
        f"**الاسم:** {member.name}\n"
        f"**المعرف:** {member.id}",
        discord.Color.red()
    )

@client.event
async def on_member_update(before, after):
    # تغيير الرتب
    if before.roles != after.roles:
        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)
        
        async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
            moderator = entry.user
            if added_roles:
                await send_log(
                    after.guild,
                    "🎭 إضافة رتبة",
                    f"**المشرف:** {moderator.mention}\n"
                    f"**العضو:** {after.mention}\n"
                    f"**الرتب المضافة:** {', '.join(role.name for role in added_roles)}",
                    discord.Color.green()
                )
            
            if removed_roles:
                await send_log(
                    after.guild,
                    "🎭 إزالة رتبة",
                    f"**المشرف:** {moderator.mention}\n"
                    f"**العضو:** {after.mention}\n"
                    f"**الرتب المحذوفة:** {', '.join(role.name for role in removed_roles)}",
                    discord.Color.red()
                )

    # تغيير الاسم المستعار
    if before.nick != after.nick:
        async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
            moderator = entry.user
            await send_log(
                after.guild,
                "📝 تغيير الاسم المستعار",
                f"**المشرف:** {moderator.mention}\n"
                f"**العضو:** {after.mention}\n"
                f"**الاسم القديم:** {before.nick}\n"
                f"**الاسم الجديد:** {after.nick}"
            )

@client.event
async def on_message_delete(message):
    if message.author.bot:
        return
    
    async for entry in message.guild.audit_logs(limit=1, action=discord.AuditLogAction.message_delete):
        moderator = entry.user
        if entry.target.id == message.author.id:
            await send_log(
                message.guild,
                "🗑️ حذف رسالة",
                f"**المشرف:** {moderator.mention}\n"
                f"**العضو:** {message.author.mention}\n"
                f"**القناة:** {message.channel.mention}\n"
                f"**المحتوى:** {message.content}",
                discord.Color.red()
            )

@client.event
async def on_message_edit(before, after):
    if before.author.bot:
        return
        
    if before.content != after.content:
        await send_log(
            after.guild,
            "✏️ تعديل رسالة",
            f"**القناة:** {after.channel.mention}\n"
            f"**العضو:** {after.author.mention}\n"
            f"**قبل:** {before.content}\n"
            f"**بعد:** {after.content}"
        )

# سجلات القنوات
@client.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
        moderator = entry.user
        await send_log(
            channel.guild,
            "📝 إنشاء قناة",
            f"**المشرف:** {moderator.mention}\n"
            f"**اسم القناة:** {channel.name}\n"
            f"**النوع:** {channel.type}\n"
            f"**الفئة:** {channel.category}",
            discord.Color.green()
        )

@client.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        moderator = entry.user
        await send_log(
            channel.guild,
            "🗑️ حذف قناة",
            f"**المشرف:** {moderator.mention}\n"
            f"**اسم القناة:** {channel.name}\n"
            f"**النوع:** {channel.type}\n"
            f"**الفئة:** {channel.category}",
            discord.Color.red()
        )

@client.event
async def on_guild_channel_update(before, after):
    if before.name != after.name:
        async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_update):
            moderator = entry.user
            await send_log(
                after.guild,
                "✏️ تعديل اسم قناة",
                f"**المشرف:** {moderator.mention}\n"
                f"**الاسم القديم:** {before.name}\n"
                f"**الاسم الجديد:** {after.name}"
            )

# سجلات الرتب
@client.event
async def on_guild_role_create(role):
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
        moderator = entry.user
        await send_log(
            role.guild,
            "👑 إنشاء رتبة",
            f"**المشرف:** {moderator.mention}\n"
            f"**اسم الرتبة:** {role.name}\n"
            f"**اللون:** {role.color}\n"
            f"**الصلاحيات:** {', '.join(perm for perm, value in role.permissions if value)}",
            discord.Color.green()
        )

@client.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        moderator = entry.user
        await send_log(
            role.guild,
            "🗑️ حذف رتبة",
            f"**المشرف:** {moderator.mention}\n"
            f"**اسم الرتبة:** {role.name}",
            discord.Color.red()
        )

@client.event
async def on_guild_role_update(before, after):
    async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
        moderator = entry.user
        if before.name != after.name:
            await send_log(
                after.guild,
                "✏️ تعديل اسم رتبة",
                f"**المشرف:** {moderator.mention}\n"
                f"**الاسم القديم:** {before.name}\n"
                f"**الاسم الجديد:** {after.name}"
            )
        
        if before.permissions != after.permissions:
            added_perms = [perm for perm, value in after.permissions if value and not getattr(before.permissions, perm)]
            removed_perms = [perm for perm, value in before.permissions if value and not getattr(after.permissions, perm)]
            
            if added_perms or removed_perms:
                description = f"**المشرف:** {moderator.mention}\n**الرتبة:** {after.name}\n"
                if added_perms:
                    description += f"**الصلاحيات المضافة:** {', '.join(added_perms)}\n"
                if removed_perms:
                    description += f"**الصلاحيات المحذوفة:** {', '.join(removed_perms)}"
                    
                await send_log(
                    after.guild,
                    "🔧 تعديل صلاحيات رتبة",
                    description
                )

# سجلات الدعوات
@client.event
async def on_invite_create(invite):
    await send_log(
        invite.guild,
        "📨 إنشاء دعوة",
        f"**المنشئ:** {invite.inviter.mention}\n"
        f"**القناة:** {invite.channel.mention}\n"
        f"**الرابط:** {invite.code}\n"
        f"**المدة:** {'غير محدود' if invite.max_age == 0 else f'{invite.max_age} ثانية'}\n"
        f"**عدد الاستخدامات:** {'غير محدود' if invite.max_uses == 0 else invite.max_uses}",
        discord.Color.green()
    )

@client.event
async def on_invite_delete(invite):
    async for entry in invite.guild.audit_logs(limit=1, action=discord.AuditLogAction.invite_delete):
        moderator = entry.user
        await send_log(
            invite.guild,
            "🗑️ حذف دعوة",
            f"**المشرف:** {moderator.mention}\n"
            f"**الرابط:** {invite.code}",
            discord.Color.red()
        )

# سجلات الصوت
@client.event
async def on_voice_state_update(member, before, after):
    async for entry in member.guild.audit_logs(limit=1):
        moderator = entry.user
        # تغيير القناة
        if before.channel != after.channel:
            if after.channel and not before.channel:
                await send_log(
                    member.guild,
                    "🎙️ انضمام للصوت",
                    f"**العضو:** {member.mention}\n"
                    f"**القناة:** {after.channel.name}"
                )
            elif before.channel and not after.channel:
                if entry.action == discord.AuditLogAction.member_disconnect:
                    await send_log(
                        member.guild,
                        "🎙️ طرد من الصوت",
                        f"**المشرف:** {moderator.mention}\n"
                        f"**العضو:** {member.mention}\n"
                        f"**القناة:** {before.channel.name}"
                    )
                else:
                    await send_log(
                        member.guild,
                        "🎙️ مغادرة الصوت",
                        f"**العضو:** {member.mention}\n"
                        f"**القناة:** {before.channel.name}"
                    )
            else:
                await send_log(
                    member.guild,
                    "🎙️ تغيير قناة صوتية",
                    f"**العضو:** {member.mention}\n"
                    f"**من:** {before.channel.name}\n"
                    f"**إلى:** {after.channel.name}"
                )
        
        # كتم الصوت
        if before.deaf != after.deaf:
            if entry.action == discord.AuditLogAction.member_update:
                await send_log(
                    member.guild,
                    "🔇 كتم الصوت",
                    f"**المشرف:** {moderator.mention}\n"
                    f"**العضو:** {member.mention}\n"
                    f"**الحالة:** {'تم كتم الصوت' if after.deaf else 'تم إلغاء كتم الصوت'}"
                )
        
        # كتم المايك
        if before.mute != after.mute:
            if entry.action == discord.AuditLogAction.member_update:
                await send_log(
                    member.guild,
                    "🔈 كتم المايك",
                    f"**المشرف:** {moderator.mention}\n"
                    f"**العضو:** {member.mention}\n"
                    f"**الحالة:** {'تم كتم المايك' if after.mute else 'تم إلغاء كتم المايك'}"
                )

@client.event
async def on_member_ban(guild, user):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        moderator = entry.user
        await send_log(
            guild,
            "🔨 حظر عضو",
            f"**المشرف:** {moderator.mention}\n"
            f"**العضو:** {user.mention}\n"
            f"**السبب:** {entry.reason or 'لم يتم تحديد سبب'}",
            discord.Color.red()
        )

@client.event
async def on_member_unban(guild, user):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.unban):
        moderator = entry.user
        await send_log(
            guild,
            "🔓 فك الحظر",
            f"**المشرف:** {moderator.mention}\n"
            f"**العضو:** {user.mention}",
            discord.Color.green()
        )

# تشغيل البوت
client.run(TOKEN) 