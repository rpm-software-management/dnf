from distutils.core import setup
setup(name="urlgrabber",
      version="0.3",
      description="high-level cross-protocol url-grabber",
      author="Michael D. Stenner, Ryan Tomayko",
      author_email="mstenner@phy.duke.edu, rtomayko@naeblis.cx",
      url="http://linux.duke.edu/projects/mini/urlgrabber/",
      license="GPL",
      packages=['URLGrabber'],
      package_dir={'URLGrabber' : ''},
      scripts=['urlgrabber'],
      data_files=[
          ('share/doc', ['README','LICENSE'])
          ],
      options = { 
        'build_py': { 'optimize': '2', 'compile' : 1 } ,
        'clean' : { 'all' : 1 }
        },
      )
