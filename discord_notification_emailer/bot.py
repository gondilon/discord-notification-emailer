import discord
import logging
import socket
import datetime
import configparser
import argparse
import clusterer
import email_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)


class EmailerBot(discord.Client):

    def __init__(self, emailer, to, *args, clustering_period=60,
                 sender=f'discordbot@{socket.gethostname()}', loop=None,
                 **options):
        """Inializes a bot that sends new messages to a email

        :param emailer: A email_tools.Emailer obj that will be used to send
        emails.
        :param clustering_period: The period of time between messages in which
        messages are grouped together in a single email.
        :param sender: The sender address of the email (Note: SMTP settings
        may override this)
        """
        self.emailer = emailer
        self.to = to
        self.sender = sender
        self.cluster_manager = clusterer.ClusterManager(self.send_email,
                                                        clustering_period)
        super().__init__(*args, loop=loop, **options)

    async def on_ready(self):
        logger.info('Bot is now online.')

    async def on_message(self, message):
        """Adds a message to the cluster"""
        self.cluster_manager.append(message)

    def send_email(self, messages):
        """
        Sends a email using the emailer with the updated messages.
        """
        channels = set([msg.channel.name for msg in messages])
        content = self._start_html()

        author_channel = ("", "")
        for message in messages:
            if (message.author, message.channel) != author_channel:
                content += self._format_header(message.author,
                                               message.channel,
                                               message.created_at)
            content += self._format_message(message)
            author_channel = (message.author, message.channel)

        content += self._end_html()
        subject = (f'{len(messages)} New Messages from Discord '
                   f'({", ".join(channels)})')
        self.emailer.send_email(self.to,
                                self.sender,
                                subject,
                                content,
                                content_type='text/html')

    def _start_html(self, style_loc='style.css'):
        """Starts the beginning of the html"""
        style = ''
        with open(style_loc) as stylesheet:
            try:
                style = stylesheet.read().replace('\n', '')
            except IOError:
                logger.warning('CSS file: %s could not be found!', style_loc)
                pass
        return f'<html><head><style>{style}</style></head><body>'

    def _end_html(self):
        """Ends the html"""
        return '</body></html>'

    def _format_message(self, message):
        """Formats a message line into html"""
        return f'<p>{message.clean_content}</p>'

    def _format_header(self, user, channel, dt):
        """Formats a header based off of a discord.User and a datetime obj into
        html
        """
        date = dt.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)
        header = (f'<br><h2>{user.name} ({channel.name})</h2>'
                  f'<span class="date">{date.strftime("%H:%M on %b %d")}'
                  f'</span>')
        return header


def configuration(filepath):
    """Reads a config file and returns a dict with it's properties"""
    reader = configparser.ConfigParser()
    reader.read(filepath)
    config = {}

    # Email
    email_config = reader['Email']
    config['to'] = email_config['to']
    config['smtp_username'] = email_config.get('smtp_username')
    config['smtp_server'] = email_config.get('smtp_server')
    config['smtp_port'] = email_config.get('smtp_port')
    config['smtp_password'] = email_config.get('smtp_password')

    # Bot Configuration
    clustering_config = reader['Clustering']
    config['period'] = int(clustering_config.get('clustering_period', 60))
    config['key'] = reader['Discord'].get('key')

    return config


def arguments():
    desc = 'A discord notification emailer'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('-c', '--config',
                        help='The filepath of the configuration file. '
                             '(Defaults to ../config.cfg)')
    return parser.parse_args()


def main(args):
    config_path = '../config.cfg'
    if args.config:
        config_path = args.config
    config = configuration(config_path)
    if 'smtp_username' in config:
        emailer = email_tools.Emailer(config['smtp_server'],
                                      config['smtp_port'],
                                      config['smtp_username'],
                                      config['smtp_password'])
    # assume it's just a plain mail server
    else:
        emailer = email_tools.Emailer(config['smtp_server'])
    bot = EmailerBot(emailer, config['to'], clustering_period=config['period'])
    bot.run(config['key'])


if __name__ == '__main__':
    main(arguments())
