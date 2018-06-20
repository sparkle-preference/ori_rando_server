import unittest
import webapp2
import StringIO
from seedgentest import SeedGenTests

class TestRunner(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		suite = unittest.TestLoader().loadTestsFromTestCase(SeedGenTests)
		stream = StringIO.StringIO()
		res = unittest.TextTestRunner(verbosity=2, stream=stream).run(suite)
		out = stream.getvalue()
		stream.close()
		self.response.status = 200 if res.wasSuccessful() else 500
		self.response.out.write(out)
