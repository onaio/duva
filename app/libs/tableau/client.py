from pathlib import Path

import tableauserverclient as TSC

from app.core.security import fernet_decrypt
from app.models import Configuration


class InvalidConfiguration(Exception):
    pass


class TableauClient:
    def __init__(self, configuration: Configuration):
        self.project_name = configuration.project_name
        self.token_name = configuration.token_name
        self.token_value = Configuration.decrypt_value(configuration.token_value)
        self.site_name = configuration.site_name
        self.server_address = configuration.server_address

    @staticmethod
    def validate_configuration(configuration):
        if isinstance(configuration, Configuration):
            access_token = fernet_decrypt(configuration.token_value)
        else:
            access_token = configuration.token_value

        tableau_auth = TSC.PersonalAccessTokenAuth(
            token_name=configuration.token_name,
            personal_access_token=access_token,
            site_id=configuration.site_name,
        )
        try:
            server = TSC.Server(configuration.server_address, use_server_version=True)
            server.auth.sign_in(tableau_auth)
            server.auth.sign_out()
        except Exception as e:
            raise InvalidConfiguration(f"Failed to validate configuration: {e}")

    def publish_hyper(self, hyper_name):
        """
        Signs in and publishes an extract directly to Tableau Online/Server
        """

        # Sign in to server
        tableau_auth = TSC.PersonalAccessTokenAuth(
            token_name=self.token_name,
            personal_access_token=self.token_value,
            site_id=self.site_name,
        )
        server = TSC.Server(self.server_address, use_server_version=True)

        print(f"Signing into {self.site_name} at {self.server_address}")
        with server.auth.sign_in(tableau_auth):
            # Define publish mode - Overwrite, Append, or CreateNew
            publish_mode = TSC.Server.PublishMode.Overwrite

            # Get project_id from project_name
            # all_projects, _ = server.projects.get()
            for project in TSC.Pager(server.projects):
                if project.name == self.project_name:
                    project_id = project.id

            # Create the datasource object with the project_id
            datasource = TSC.DatasourceItem(project_id)

            print(f"Publishing {hyper_name} to {self.project_name}...")

            path_to_database = Path(hyper_name)
            # Publish datasource
            datasource = server.datasources.publish(
                datasource, path_to_database, publish_mode
            )
            print("Datasource published. Datasource ID: {0}".format(datasource.id))
