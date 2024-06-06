### SearchAssist Extraction Utility
 
## Prerequisites

* **Python 3.9.7:**
  Installing a specific version of python and making a virtual environment for it:
* Current Latest Version for setup: **3.9.7** </br>

  Please make sure all the OS level dependencies required for python configuration are installed:
  [# For yum-based systems (like CentOS)]

       - $ sudo yum -y groupinstall "Development Tools"
       - $ sudo yum -y install gcc openssl-devel bzip2-devel libffi-devel sqlite-devel dnf xz-devel
       - $ sudo apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev xz-utils tk-dev

  Run the below commands to Install latest version of Python

        - Cd /data/
        - wget "https://www.python.org/ftp/python/3.9.7/Python-3.9.7.tgz"
        - tar -zxvf Python-3.9.7.tgz
        - [move into the extracted directory] 
        - ./configure --prefix=/data/Python-3.9.7/ --enable-loadable-sqlite-extensions
        - make install
        - [global pip upgrade] /data/Python-3.9.7/bin/python3.9 -m pip install --upgrade pip==22.2.2
             Make a virtual environment and activate it:

      Create and Activate virtual environment:
      
        - cd /data
        - /data/Python-3.9.7/bin/python3.9 -m venv py3.9.7
        - source /data/py3.9.7/bin/activate

## Configuration Step

***Step 1:** **Clone Findly Repo from GitHub :** 
   * Find the repository here: <br />
     `git@github.com:Koredotcom/SearchAssist-Toolkit.git` <br /> 

* **Step 2:** **Activate virtual environment:** Execute the following command with required changes in it to activate the virtual environment 
       <br> `source virtual_environments_folder_location/virtualenv_name/bin/activate`<br>

    ### SnippetExtractionService Server Setup
* **Step 1:** **Install requirements for the project:** <br/>
        - Run the following command to install requirements <br/>
              `pip install -r requirements.txt` <br/>
        - <b>If there are any errors in running requirements file for lxml package, need to install below dependencies</b></br>
        - sudo apt-get install libxml2-dev libxslt-dev python3-dev <br/>
        - Run `pip list` command to verify all the installed requirements <br/>

### To run the script using below command 
 `streamlit run Utilities/SnippetExtraction/SnippetExtractionService.py --server.enableXsrfProtection=false --server.enableCORS=false --server.enableWebsocketCompression=false`
       
      
