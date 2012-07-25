import struct
import sys
import os
import base64
import zlib
from xmlrpc.client import ServerProxy, Error

class SubtitleDownload:
    '''Traverses a directory and all subdirectories and downloads subtitles.
    
    Relies on an undocumented OpenSubtitles feature where subtitles seems to be
    sorted by filehash and popularity.
    '''

    api_url = 'http://api.opensubtitles.org/xml-rpc'
    login_token = None
    server = None
    moviefiles = []
    movie_exts = (".avi", ".mkv", ".mp4")
    subb_exts = (".srt", ".sub", ".mpl")

    def __init__(self, movie_path, lang = "en"):
        print("OpenSubtitles Subtitle Downloader".center(78))
        print("===================================".center(78))
        self.server = ServerProxy(self.api_url, verbose=False)
        self.lang_id = lang

        # Traverse the directory tree and select all movie files
        for root, _, files in os.walk(movie_path):
            for file in files:
                if self.is_movie(file):
                    file_path = os.path.join(root, file)
                    if not self.subtitles_already_present(file_path):
                        print("Found: " + file)
                        filehash = self.hashFile(file_path)
                        filesize = os.path.getsize(file_path)
                        self.moviefiles.append({'dir': root,
                                                'file': file,
                                                'hash': filehash,
                                                'size': filesize,
                                                'subtitleid': None})

        try:
            print("Login...")
            self.login()
            
            print("Searching for subtitles...")
            self.search_subtitles()
            
            print("Logout...")
            self.logout()
        except Error as e:
            print("XML-RPC error:", e)
        except UserWarning as uw:
            print(uw)
    
    def login(self):
        '''Log in to OpenSubtitles'''
        resp = self.server.LogIn('', '', 'en', 'OS Test User Agent')
        self.check_status(resp)
        self.login_token = resp['token']
    
    def logout(self):
        '''Log out from OpenSubtitles'''
        resp = self.server.LogOut(self.login_token)
        self.check_status(resp)
    
    def search_subtitles(self):
        '''Search OpenSubtitles for matching subtitles'''
        search = []
        for movie in self.moviefiles:
            search.append({'sublanguageid': self.lang_id,
                           'moviehash': movie['hash'], 
                           'moviebytesize': str(movie['size'])})

        # fixes weird problem where subs aren't found when only searching
        # for one movie.
        if len(search) == 1:
            search.append(search[0])

        resp = self.server.SearchSubtitles(self.login_token, search)
        self.check_status(resp)

        if resp['data'] == False:
            print("No subtitles found")
            return
        
        subtitles = []
        for result in resp['data']:
            if int(result['SubBad']) != 1:
                subtitles.append({'subid': result['IDSubtitleFile'],
                                  'hash': result['MovieHash']})
        
        downloadable_subs = subtitles[:]
        hash = None
        for s in subtitles:
            if hash == s['hash']:
                downloadable_subs.remove(s)
            hash = s['hash']
            
        for ds in downloadable_subs:
            sub = self.download_subtitles(ds)
            for movie in self.moviefiles:
                if movie['hash'] == ds['hash']:
                    print("Saving subtitle for: " + movie['file'])
                    filename = os.path.join(movie['dir'], os.path.splitext(movie['file'])[0] + ".srt")
                    file = open(filename, "wb")
                    file.write(sub)
                    file.close()
    
    def download_subtitles(self, subtitle):
        resp = self.server.DownloadSubtitles(self.login_token, [subtitle['subid']])
        self.check_status(resp)
        decoded = base64.standard_b64decode(resp['data'][0]['data'].encode('ascii'))
        decompressed = zlib.decompress(decoded, 15 + 32)
        return decompressed

    def is_movie(self, file):
        return os.path.splitext(file.lower())[1] in self.movie_exts

    def subtitles_already_present(self, file):
        file_base = os.path.splitext(file.lower())[0]
        for ext in self.subb_exts:
            if os.path.exists(file_base + ext):
                return True
        return False

    def check_status(self, resp):
        '''Check the return status of the request.
        
        Anything other than "200 OK" raises a UserWarning
        '''
        if resp['status'].upper() != '200 OK':
            raise UserWarning("Response error from " + self.api_url + ". Response status was: " + resp['status'])

    def hashFile(self, name):
        '''Calculates the hash value of a movie.
        
        Copied from OpenSubtitles own examples: 
            http://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes
        '''
        try: 
            longlongformat = 'q'  # long long 
            bytesize = struct.calcsize(longlongformat) 
            
            f = open(name, "rb")
            
            filesize = os.path.getsize(name)
            hash = filesize 
            
            if filesize < 65536 * 2: 
                return "SizeError" 
            
            for x in range(65536//bytesize): 
                buffer = f.read(bytesize) 
                (l_value,)= struct.unpack(longlongformat, buffer)  
                hash += l_value 
                hash = hash & 0xFFFFFFFFFFFFFFFF #to remain as 64bit number  
            
            f.seek(max(0,filesize-65536),0) 
            for x in range(65536//bytesize): 
                buffer = f.read(bytesize) 
                (l_value,)= struct.unpack(longlongformat, buffer)  
                hash += l_value 
                hash = hash & 0xFFFFFFFFFFFFFFFF 
            
            f.close() 
            returnedhash =  "%016x" % hash 
            return returnedhash 
        except(IOError): 
            return "IOError"


if __name__ == '__main__':
    import os
    cwd = os.getcwd()
    if len(sys.argv) > 1:
        cwd = sys.argv[1]
    # in order to download non english subtitles add second argument
    # second language argument such as 'fre' or 'pol'
    downloader = SubtitleDownload(cwd)

