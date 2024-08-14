import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import requests
from PIL import Image, ImageTk
import io
import gbif_dl
import threading
import os 
import time
import random

class GBIFDownloader(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("GBIF Image Downloader")

        self.download_stats = None

        # Set application icon
        self.icon_path = "gbif_dl_icon.png"  # Placeholder path for the logo
        self.icon_image = tk.PhotoImage(file=self.icon_path)
        self.iconphoto(False, self.icon_image)

        # Banner with logo and buttons
        self.banner_frame = ttk.Frame(self)
        self.banner_frame.grid(row=0, column=0, columnspan=4, sticky="EW", padx=10, pady=10)
        
        self.logo = tk.PhotoImage(file=self.icon_path)  # Placeholder path for the logo
        ttk.Label(self.banner_frame, image=self.logo).pack(side="right", padx=10)

        ttk.Button(self.banner_frame, text="Save Query", command=self.save_query).pack(side="left", padx=10)
        ttk.Button(self.banner_frame, text="Load Query", command=self.load_query).pack(side="left", padx=10)

        self.help_button = ttk.Button(self.banner_frame, text="Help", command=self.show_help)
        self.help_button.pack(side="right", padx=10)

        self.query = {}

        # Output directory
        self.output_dir = tk.StringVar()
        output_frame = ttk.Frame(self.banner_frame)
        output_frame.pack(side="right", padx=10, pady=5)
        ttk.Label(output_frame, text="Output Directory:").pack(side="left", padx=5)
        ttk.Entry(output_frame, textvariable=self.output_dir, width=50).pack(side="left", padx=5)
        ttk.Button(output_frame, text="Browse", command=self.browse_directory).pack(side="left", padx=5)

        # Create the notebook (tabbed interface)
        self.notebook = ttk.Notebook(self, padding=10)
        self.notebook.grid(row=1, column=0, columnspan=3, sticky="NSEW")

        # Query builder

        # Possible query keys from the GBIF occurrence API
        self.occurrence_keys = sorted(['key', 'datasetKey', 'publishingOrgKey', 'networkKeys', 'installationKey', 'hostingOrganizationKey',
                                       'publishingCountry', 'protocol', 'lastCrawled', 'lastParsed', 'crawlId', 'extensions', 'basisOfRecord',
                                       'occurrenceStatus', 'taxonKey', 'kingdomKey', 'phylumKey', 'classKey', 'orderKey', 'familyKey', 'genusKey',
                                       'speciesKey', 'acceptedTaxonKey', 'scientificName', 'acceptedScientificName', 'kingdom', 'phylum', 'order',
                                       'family', 'genus', 'species', 'genericName', 'specificEpithet', 'taxonRank', 'taxonomicStatus',
                                       'iucnRedListCategory', 'decimalLatitude', 'decimalLongitude', 'continent', 'gadm', 'year', 'month', 'day',
                                       'eventDate', 'startDayOfYear', 'endDayOfYear', 'issues', 'modified', 'lastInterpreted', 'license',
                                       'isSequenced', 'identifiers', 'media', 'facts', 'relations', 'institutionKey', 'isInCluster',
                                       'recordedBy', 'identifiedBy', 'geodeticDatum', 'class', 'countryCode', 'recordedByIDs', 'identifiedByIDs',
                                       'gbifRegion', 'country', 'publishedByGbifRegion', 'recordNumber', 'identifier', 'catalogNumber', 'habitat',
                                       'institutionCode', 'locality', 'eventRemarks', 'gbifID', 'collectionCode', 'occurrenceID', 'higherClassification'])

        self.query_frame = ttk.Frame(self.notebook)
        self.query_frame.grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="NSEW")

        self.query_canvas = tk.Canvas(self.query_frame)
        self.query_scrollbar = ttk.Scrollbar(self.query_frame, orient="vertical", command=self.query_canvas.yview)
        self.query_content = ttk.Frame(self.query_canvas)

        self.query_content.bind(
            "<Configure>",
            lambda e: self.query_canvas.configure(
                scrollregion=self.query_canvas.bbox("all")
            )
        )

        self.query_canvas.create_window((0, 0), window=self.query_content, anchor="nw")
        self.query_canvas.configure(yscrollcommand=self.query_scrollbar.set)

        self.query_canvas.grid(row=0, column=0, columnspan=3, sticky="NSEW")
        self.query_scrollbar.grid(row=0, column=3, sticky="NS")

        self.query_entries = []
        for _ in range(3):  # Show 3 queries initially
            self.add_query_row()

        # Add buttons below the query content
        button_frame = ttk.Frame(self.query_frame)
        button_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=5, sticky="EW")

        ttk.Button(button_frame, text="Add Attribute", command=self.add_query_row, width=25).grid(row=0, column=0, padx=10, pady=5)
        ttk.Button(button_frame, text="Remove Attribute", command=self.remove_query_row, width=25).grid(row=0, column=1, padx=10, pady=5)

        self.doi_frame = ttk.Frame(self.notebook)
        self.doi_frame.grid(row=0, column=0, padx=10, pady=5, sticky="NSEW")
        self.doi_var = tk.StringVar()
        # Make the label and entry float in the vertical center
        ttk.Label(self.doi_frame, text="DOI:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(self.doi_frame, textvariable=self.doi_var, width=50).grid(row=0, column=1, padx=5, pady=5)

        # Add frames to the notebook
        self.notebook.add(self.query_frame, text="Query Builder")
        self.notebook.add(self.doi_frame, text="DWCA DOI")

        # Image gallery
        self.gallery_frame = ttk.LabelFrame(self, text="Image Preview Gallery")
        self.gallery_frame.grid(row=1, column=3, rowspan=3, padx=10, pady=5, sticky="NSEW")

        self.gallery_canvas = tk.Canvas(self.gallery_frame)
        self.gallery_scrollbar = ttk.Scrollbar(self.gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
        self.gallery_container = ttk.Frame(self.gallery_canvas)

        self.gallery_container.bind(
            "<Configure>",
            lambda e: self.gallery_canvas.configure(
                scrollregion=self.gallery_canvas.bbox("all")
            )
        )

        self.gallery_canvas.create_window((0, 0), window=self.gallery_container, anchor="nw")
        self.gallery_canvas.configure(yscrollcommand=self.gallery_scrollbar.set)

        self.gallery_canvas.pack(side="left", fill="both", expand=True)
        self.gallery_scrollbar.pack(side="right", fill="y")

        # Start/Stop buttons
        self.start_button = ttk.Button(self, text="Begin Download", style="TButton", command=self.start_download)
        self.start_button.grid(row=4, column=0, columnspan=3, padx=10, pady=10, sticky="EW")

        self.stop_button = ttk.Button(self, text="Stop Download", style="TButton", command=self.stop_download, state="disabled")
        self.stop_button.grid(row=4, column=3, columnspan=2, padx=10, pady=10, sticky="EW")

        # Statistics display
        self.stats_label = ttk.Label(self, text="Download Status: Waiting to start...", anchor="w")
        self.stats_label.grid(row=5, column=0, columnspan=4, padx=10, pady=10, sticky="EW")

        self.update_idletasks()  # Update "requested size" from geometry manager
        self.geometry(f'{self.winfo_reqwidth()}x{self.winfo_reqheight()}')

    def show_help(self) -> None:
        """
        Display help text in a messagebox.
        """
        help_text = """GBIF Image Downloader
        \n1. Select a directory to save downloaded images to
        \n2a. Build a query using the Query Builder tab. Type keys into the left column and values into the right column,. Click "Add Attribute" to add more attributes to the query, or "Remove Attribute" to remove the last attribute.
        Several values can be included for each key by adding multiple rows with the same key.
        \n2b. Alternatively, enter a DOI in the DWCA DOI tab to download images from a pre-existing Darwin Core Archive.
        \n3. Queries can be saved and loaded using the "Save Query" and "Load Query" buttons.
        \n3. Click "Begin Download" to start downloading images. Click "Stop Download" to cancel the download.
        \n4. The Image Gallery will display images as they are downloaded.
        \n5. The "Download Status" label will display the number of successful, passed, and failed downloads.
        """
        messagebox.showinfo("Help", help_text)

    def browse_directory(self) -> None:
        '''
        Open a file dialog to select a directory and set the output directory to the selected directory.
        Display images in the gallery from the selected directory should any exist.
        '''
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir.set(directory)
        self.display_images()

    def add_query_row(self) -> None:
        """
        Add a new row to the query builder widget with a combobox to select the key and an entry to input the value.
        """
        row = len(self.query_entries)
        if row >= 5:
            self.query_canvas.yview_moveto(1.0)  # Scroll to the bottom to show the new row
        key_var = tk.StringVar()
        value_var = tk.StringVar()
        key_entry = ttk.Combobox(self.query_content, textvariable=key_var, width=25, values=self.occurrence_keys)
        value_entry = ttk.Entry(self.query_content, textvariable=value_var, width=25)
        key_entry.grid(row=row, column=0, padx=10, pady=5)
        value_entry.grid(row=row, column=1, padx=10, pady=5)
        self.query_entries.append((key_var, value_var, key_entry, value_entry))

    def remove_query_row(self) -> None:
        """
        Remove the last row from the query builder widget.
        """
        if self.query_entries:
            key_var, value_var, key_entry, value_entry = self.query_entries.pop()
            key_entry.destroy()
            value_entry.destroy()

    def save_query(self) -> None:
        """
        Save the current query in the query builder to a JSON file.
        """
        self.build_query()
        if not self.query:
            messagebox.showerror("Error", "Please build a query.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'w') as file:
                json.dump(self.query, file)

    def load_query(self) -> None:
        """
        Load a query from a JSON file and populate the query builder with the loaded query and show it in the query builder.
        """
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'r') as file:
                self.query = json.load(file)
            self.populate_query_builder()

    def populate_query_builder(self) -> None:
        """
        Populate the query builder with a loaded query.
        """
        for _, _, key_entry, value_entry in self.query_entries:
            key_entry.destroy()
            value_entry.destroy()
        self.query_entries.clear()

        for key, values in self.query.items():
            for value in values:
                key_var = tk.StringVar(value=key)
                value_var = tk.StringVar(value=value)
                key_entry = ttk.Combobox(self.query_content, textvariable=key_var, width=25, values=self.occurence_keys)
                value_entry = ttk.Entry(self.query_content, textvariable=value_var, width=25)
                row = len(self.query_entries)
                key_entry.grid(row=row, column=0, padx=10, pady=5)
                value_entry.grid(row=row, column=1, padx=10, pady=5)
                self.query_entries.append((key_var, value_var, key_entry, value_entry))

    def start_download(self) -> None:
        """
        Start the appropriate download process in a separate thread depending on the current tab.
        """
        self.stats_label.config(text="Download Status: Downloading...")
        self.start_button.config(state="disabled")
        if self.notebook.index(self.notebook.select()) == 0:
            threading.Thread(target=self.download_images_query, name="download_thread", daemon=True).start()
        else:
            threading.Thread(target=self.download_images_doi, name="download_thread", daemon=True).start()

    def stop_download(self):
        # Set the stop event to signal the thread to stop
        # TODO: Implement a way to stop the download, requires changes to gbif-dl
        pass

    def download_images_query(self) -> None:
        """
        Download images from the GBIF occurence API using the query built in the query builder and gbif-dl.
        Display a sample of the downloaded images in the gallery after complete.
        """
        self.build_query()
        print("Query:\n", self.query)
        if not self.output_dir.get():
            self.stats_label.config(text="Download Status: "+self.download_stats)
            self.start_button.config(state="normal")
            messagebox.showerror("Error", "Please specify an output directory.")
            return
        if not self.query:
            messagebox.showerror("Error", "Please build a query.")
            self.stats_label.config(text="Download Status: "+self.download_stats)
            self.start_button.config(state="normal")
            return
        
        data_generator = gbif_dl.api.generate_urls(queries=self.query)
        self.download_stats = gbif_dl.dl_async.download(data_generator, root=self.output_dir.get())
        # Set content of stats_text
        self.stats_label.config(text="Download Status: "+str(self.download_stats))
        self.start_button.config(state="normal")
        
        self.display_images() # TODO: Display images as they are downloaded rather than after the download is complete

    def download_images_doi(self) -> None:
        """
        Download images from the GBIF occurence API using a DOI to a pre-existing DWCA and gbif-dl.
        """
        if not self.output_dir.get():
            self.stats_label.config(text="Download Status: DOI not entered.")
            self.start_button.config(state="normal")
            return
        data_generator = gbif_dl.dwca.generate_urls(self.doi_var.get(), dwca_root_path="dwcas")
        self.download_stats = gbif_dl.dl_async.download(data_generator, root=self.output_dir.get())
        self.stats_label.config(text="Download Status: "+str(self.download_stats))
        self.start_button.config(state="normal")

        self.display_images()

    def build_query(self) -> None:
        """
        Build a query dictionary from the text in the query builder widget
        """
        self.query.clear()
        for key_var, value_var, _, _ in self.query_entries:
            key = key_var.get().strip()
            value = value_var.get().strip()
            if key and value:
                if key not in self.query:
                    self.query[key] = []
                self.query[key].append(value)

    def display_images(self) -> None:
        '''
        Display images in the gallery from the output directory.
        '''
        # Clear the gallery
        for widget in self.gallery_container.winfo_children():
            widget.destroy()

        columns = 4 

        # Reservoir sampling to store sampled random images
        reservoir = []
        sample_size = 50
        count = 0
        
        output_dir = os.path.normpath(self.output_dir.get())

        # Traverse the directory and subdirectories
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if file.endswith(".jpg") or file.endswith(".jpeg") or file.endswith(".png"):
                    full_path = os.path.join(root, file)
                    if count < sample_size:
                        reservoir.append(full_path)
                    else:
                        r = random.randint(0, count)
                        if r < sample_size:
                            reservoir[r] = full_path
                    count += 1

        # Display the images in the gallery
        for index, image_path in enumerate(reservoir):
            img = Image.open(image_path)
            img.thumbnail((100, 100))
            img_tk = ImageTk.PhotoImage(img)
            label = ttk.Label(self.gallery_container, image=img_tk)
            label.image = img_tk
            row = index // columns
            column = index % columns
            label.grid(row=row, column=column, padx=5, pady=5)

        self.update_idletasks()  # Update "requested size" from geometry manager

        # Scroll to the bottom to show the new images
        self.gallery_canvas.yview_moveto(1.0)


if __name__ == "__main__":
    app = GBIFDownloader()
    app.mainloop()
