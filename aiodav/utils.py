from typing import Union
from aiodav.exceptions import *
from aiodav.urn import Urn

import lxml.etree as etree
from urllib.parse import unquote, urlsplit, urlparse
from io import BytesIO

class WebDavXmlUtils:
    def __init__(self) -> None:
        pass

    @staticmethod
    def parse_get_list_info_response(content):
        """
        Parses of response content XML from WebDAV server and extract file and directory infos

        :param content: the XML content of HTTP response from WebDAV server for getting list of files by remote path.
        :return: list of information, the information is a dictionary and it values with following keys:
                 `created`: date of resource creation,
                 `name`: name of resource,
                 `size`: size of resource,
                 `modified`: date of resource modification,
                 `etag`: etag of resource,
                 `isdir`: type of resource,
                 `path`: path of resource.
        """
        try:
            tree = etree.fromstring(content.encode())
            infos = []
            for response in tree.findall(".//{DAV:}response"):
                href_el = next(iter(response.findall(".//{DAV:}href")), None)
                if href_el is None:
                    continue
                path = unquote(urlsplit(href_el.text).path)
                info = dict()
                is_dir = len(response.findall(".//{DAV:}collection")) > 0
                info = WebDavXmlUtils.get_info_from_response(response)
                info['isdir'] = is_dir
                info['path'] = path
                infos.append(info)
            return infos
        except etree.XMLSyntaxError:
            return list()

    @staticmethod
    def parse_get_list_response(content):
        """Parses of response content XML from WebDAV server and extract file and directory names.

        :param content: the XML content of HTTP response from WebDAV server for getting list of files by remote path.
        :return: list of extracted file or directory names.
        """
        try:
            tree = etree.fromstring(content.encode())
            urns = []
            for response in tree.findall(".//{DAV:}response"):
                href_el = next(iter(response.findall(".//{DAV:}href")), None)
                if href_el is None:
                    continue
                href = Urn.separate + unquote(urlsplit(href_el.text).path)
                is_dir = len(response.findall(".//{DAV:}collection")) > 0
                urns.append(Urn(href, is_dir))
            return urns
        except etree.XMLSyntaxError:
            return list()

    @staticmethod
    def create_free_space_request_content():
        """Creates an XML for requesting of free space on remote WebDAV server.

        :return: the XML string of request content.
        """
        root = etree.Element("propfind", xmlns="DAV:")
        prop = etree.SubElement(root, "prop")
        etree.SubElement(prop, "quota-available-bytes")
        etree.SubElement(prop, "quota-used-bytes")
        tree = etree.ElementTree(root)
        return WebDavXmlUtils.etree_to_string(tree)

    @staticmethod
    def parse_free_space_response(content, hostname):
        """Parses of response content XML from WebDAV server and extract an amount of free space.

        :param content: the XML content of HTTP response from WebDAV server for getting free space.
        :param hostname: the server hostname.
        :return: an amount of free space in bytes.
        """
        try:
            tree = etree.fromstring(content.encode())
            node = tree.find('.//{DAV:}quota-available-bytes')
            if node is not None:
                return int(node.text)
            else:
                raise MethodNotSupported(name='free', server=hostname)
        except TypeError:
            raise MethodNotSupported(name='free', server=hostname)
        except etree.XMLSyntaxError:
            return -1 # TODO: replace

    @staticmethod
    def get_info_from_response(response):
        """ Get information attributes from response

        :param response: XML object of response for the remote resource defined by path
        :return: a dictionary of information attributes and them values with following keys:
                 `created`: date of resource creation,
                 `name`: name of resource,
                 `size`: size of resource,
                 `modified`: date of resource modification,
                 `etag`: etag of resource
        """
        find_attributes = {
            'created': ".//{DAV:}creationdate",
            'name': ".//{DAV:}displayname",
            'size': ".//{DAV:}getcontentlength",
            'modified': ".//{DAV:}getlastmodified",
            'etag': ".//{DAV:}getetag",
        }
        info = dict()
        for (name, value) in find_attributes.items():
            info[name] = response.findtext(value)
        return info

    @staticmethod
    def parse_info_response(content, path, hostname):
        """Parses of response content XML from WebDAV server and extract an information about resource.

        :param content: the XML content of HTTP response from WebDAV server.
        :param path: the path to resource.
        :param hostname: the server hostname.
        :return: a dictionary of information attributes and them values with following keys:
                 `created`: date of resource creation,
                 `name`: name of resource,
                 `size`: size of resource,
                 `modified`: date of resource modification,
                 `etag`: etag of resource.
        """
        response = WebDavXmlUtils.extract_response_for_path(content=content, path=path, hostname=hostname)
        return WebDavXmlUtils.get_info_from_response(response)

    @staticmethod
    def parse_is_dir_response(content, path, hostname):
        """Parses of response content XML from WebDAV server and extract an information about resource.

        :param content: the XML content of HTTP response from WebDAV server.
        :param path: the path to resource.
        :param hostname: the server hostname.
        :return: True in case the remote resource is directory and False otherwise.
        """
        response = WebDavXmlUtils.extract_response_for_path(content=content, path=path, hostname=hostname)
        resource_type = response.find(".//{DAV:}resourcetype")
        if resource_type is None:
            raise MethodNotSupported(name="is_dir", server=hostname)
        dir_type = resource_type.find("{DAV:}collection")

        return True if dir_type is not None else False

    @staticmethod
    def create_get_property_request_content(option):
        """Creates an XML for requesting of getting a property value of remote WebDAV resource.

        :param option: the property attributes as dictionary with following keys:
                       `namespace`: (optional) the namespace for XML property which will be get,
                       `name`: the name of property which will be get.
        :return: the XML string of request content.
        """
        root = etree.Element("propfind", xmlns="DAV:")
        prop = etree.SubElement(root, "prop")
        etree.SubElement(prop, option.get('name', ""), xmlns=option.get('namespace', ""))
        tree = etree.ElementTree(root)
        return WebDavXmlUtils.etree_to_string(tree)

    @staticmethod
    def parse_get_property_response(content, name):
        """Parses of response content XML from WebDAV server for getting metadata property value for some resource.

        :param content: the XML content of response as string.
        :param name: the name of property for finding a value in response
        :return: the value of property if it has been found or None otherwise.
        """
        tree = etree.fromstring(content.encode())
        return tree.xpath('//*[local-name() = $name]', name=name)[0].text

    @staticmethod
    def create_set_property_batch_request_content(options):
        """Creates an XML for requesting of setting a property values for remote WebDAV resource in batch.

        :param options: the property attributes as list of dictionaries with following keys:
                       `namespace`: (optional) the namespace for XML property which will be set,
                       `name`: the name of property which will be set,
                       `value`: (optional) the value of property which will be set. Defaults is empty string.
        :return: the XML string of request content.
        """
        root_node = etree.Element('propertyupdate', xmlns='DAV:')
        set_node = etree.SubElement(root_node, 'set')
        prop_node = etree.SubElement(set_node, 'prop')
        for option in options:
            opt_node = etree.SubElement(prop_node, option['name'], xmlns=option.get('namespace', ''))
            opt_node.text = option.get('value', '')
        tree = etree.ElementTree(root_node)
        return WebDavXmlUtils.etree_to_string(tree)

    @staticmethod
    def etree_to_string(tree):
        """Creates string from lxml.etree.ElementTree with XML declaration and UTF-8 encoding.

        :param tree: the instance of ElementTree
        :return: the string of XML.
        """
        buff = BytesIO()
        tree.write(buff, xml_declaration=True, encoding='UTF-8')
        return buff.getvalue()

    @staticmethod
    def extract_response_for_path(content, path, hostname):
        """Extracts single response for specified remote resource.

        :param content: raw content of response as string.
        :param path: the path to needed remote resource.
        :param hostname: the server hostname.
        :return: XML object of response for the remote resource defined by path.
        """
        prefix = urlparse(hostname).path
        try:
            tree = etree.fromstring(content.encode())
            responses = tree.findall("{DAV:}response")
            n_path = Urn.normalize_path(path)

            for resp in responses:
                href = resp.findtext("{DAV:}href")

                if Urn.compare_path(n_path, href) is True:
                    return resp
                href_without_prefix = href[len(prefix):] if href.startswith(prefix) else href
                if Urn.compare_path(n_path, href_without_prefix) is True:
                    return resp
            raise RemoteResourceNotFound(path)
        except etree.XMLSyntaxError:
            raise MethodNotSupported(name="is_dir", server=hostname)
