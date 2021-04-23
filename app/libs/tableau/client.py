import tableauserverclient as TSC

from pathlib import Path

from app.models import Configuration


class TableauClient:
    def __init__(self, configuration: Configuration):
        self.project_name = configuration.project_name
        self.token_name = configuration.token_name
        self.token_value = Configuration.decrypt_value(configuration.token_value)
        self.site_name = configuration.site_name
        self.server_address = configuration.server_address

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
