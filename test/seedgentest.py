
import unittest
import webapp2

# from the app main.py
import main

class SeedGenTests(unittest.TestCase):
	def test_make_1p_seeds(self):
	
		for url in [
		"/getseed?m=shards&vars=forcetrees&lps=normal|speed|lure|dboost-light&s=0&pc=1&sym=1&pd=normal&gnm=balanced&p=1",
		"/getseed?m=clues&vars=forcetrees&lps=normal|speed|lure|dboost-light&s=1&pc=1&sym=1&pd=normal&gnm=balanced&p=1",
		"/getseed?m=limitkeys&vars=forcetrees&lps=normal|speed|lure|dboost-light&s=1&pc=1&sym=1&pd=normal&gnm=balanced&p=1",
		"https://8080-dot-3616814-dot-devshell.appspot.com/getseed?m=shards&vars=forcetrees&lps=normal|speed|lure|dboost-light&s=2&pc=1&sym=4&pd=normal&gnm=balanced&gid=1&p=1"
		]:
			request = webapp2.Request.blank(url)
			response = request.get_response(main.app)
			self.assertEqual(response.body.count("\n"), 249)
			self.assertEqual(response.status_int, 200)

	def test_main_page_loads(self):
		# Build a request object passing the URI path to be tested.
		# You can also pass headers, query arguments etc.
		request = webapp2.Request.blank('/')
		response = request.get_response(main.app)
		self.assertEqual(response.status_int, 200)
	 
