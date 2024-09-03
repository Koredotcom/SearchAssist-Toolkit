from resources.ChunkingByGPT.app import CHunkingByGPT


chunker = CHunkingByGPT('Your Key Here','Your Model name here')

'''Your can use any one of below examples'''

'''exapmle to chunk single PDF''' 
# chunker.chunk_single_pdf(timer=True,pdf_path=r'Sample File path',display_flag=False,save_flag=True)


'''exapmle to chunk Multiple PDF''' 
# chunker.chunk_multiple_pdf(timer=True,folder_path=r'Sample Folder Path',display_flag=False,save_flag=True)